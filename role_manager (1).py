#!/usr/bin/env python3
"""
Discord Role Manager — Local Add/Remove Script
------------------------------------------------
Finds every user who reacted to a message (or voted on a poll message)
and adds or removes a specified role from each of them.

This script is meant to be run once from the command line. It logs in,
performs the requested action, prints a log of what happened, and exits.
It does NOT run as a persistent bot / gateway listener beyond the single
run needed to fetch the data and apply role changes.

Usage:
    python role_manager.py --guild-id 123 --message-id 456 --role-id 789 --action add
    python role_manager.py --guild-id 123 --message-id 456 --role-id 789 --action remove --channel-id 999

See README.md for full setup instructions.
"""

import argparse
import asyncio
import os
import sys

import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Add or remove a Discord role from everyone who reacted to / voted on a message."
    )
    parser.add_argument("--guild-id", type=int, required=True, help="Discord Server (Guild) ID")
    parser.add_argument("--message-id", type=int, required=True, help="Discord Message ID")
    parser.add_argument("--role-id", type=int, required=True, help="Discord Role ID to add/remove")
    parser.add_argument(
        "--action",
        type=str,
        required=True,
        choices=["add", "remove"],
        help="Whether to ADD or REMOVE the role",
    )
    parser.add_argument(
        "--channel-id",
        type=int,
        required=False,
        default=None,
        help="Optional: Channel ID where the message lives. "
        "If omitted, the script will search all text channels in the server.",
    )
    parser.add_argument(
        "--include-bots",
        action="store_true",
        help="Optional: also apply the role change to bot accounts that reacted/voted (default: skipped).",
    )
    return parser.parse_args()


async def find_message(guild: discord.Guild, message_id: int, channel_id: int | None):
    """Locate the target message, either in a given channel or by scanning all text channels."""
    if channel_id:
        channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            raise RuntimeError(
                f"Message {message_id} was not found in channel {channel_id}."
            )

    # No channel given -> search every text channel the bot can see.
    for channel in guild.text_channels:
        try:
            message = await channel.fetch_message(message_id)
            if message:
                return message
        except (discord.NotFound, discord.Forbidden):
            continue
    raise RuntimeError(
        f"Message {message_id} was not found in any channel the bot can access in this server. "
        "Try passing --channel-id explicitly."
    )


async def collect_reaction_users(message: discord.Message, include_bots: bool) -> dict[int, discord.User]:
    """Collect every unique user who reacted to the message with any emoji."""
    users: dict[int, discord.User] = {}
    for reaction in message.reactions:
        async for user in reaction.users():
            if user.bot and not include_bots:
                continue
            users[user.id] = user
    return users


async def collect_poll_voters(message: discord.Message, include_bots: bool) -> dict[int, discord.User]:
    """Collect every unique user who voted on any answer of a poll message (if present)."""
    users: dict[int, discord.User] = {}
    poll = getattr(message, "poll", None)
    if not poll:
        return users

    for answer in poll.answers:
        async for user in answer.voters():
            if user.bot and not include_bots:
                continue
            users[user.id] = user
    return users


async def apply_role(
    guild: discord.Guild,
    users: dict[int, discord.User],
    role: discord.Role,
    action: str,
):
    """Add or remove `role` for each user in `users`, logging every outcome."""
    added, removed, skipped, failed = [], [], [], []

    for user_id, user in users.items():
        try:
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        except discord.NotFound:
            failed.append((user, "not a member of this server"))
            continue
        except discord.HTTPException as e:
            failed.append((user, f"fetch error: {e}"))
            continue

        has_role = role in member.roles

        try:
            if action == "add":
                if has_role:
                    skipped.append((user, "already has the role"))
                    continue
                await member.add_roles(role, reason="role_manager.py: add via reaction/poll")
                added.append(user)
            else:  # remove
                if not has_role:
                    skipped.append((user, "does not have the role"))
                    continue
                await member.remove_roles(role, reason="role_manager.py: remove via reaction/poll")
                removed.append(user)
        except discord.Forbidden:
            failed.append((user, "missing permissions (check role hierarchy / bot permissions)"))
        except discord.HTTPException as e:
            failed.append((user, f"Discord API error: {e}"))

    return added, removed, skipped, failed


def log_results(added, removed, skipped, failed, action):
    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)

    if action == "add":
        print(f"\nRole ADDED to {len(added)} user(s):")
        for u in added:
            print(f"  + {u} (ID: {u.id})")
    else:
        print(f"\nRole REMOVED from {len(removed)} user(s):")
        for u in removed:
            print(f"  - {u} (ID: {u.id})")

    print(f"\nSkipped {len(skipped)} user(s) (no change needed):")
    for u, reason in skipped:
        print(f"  ~ {u} (ID: {u.id}) — {reason}")

    if failed:
        print(f"\nFailed for {len(failed)} user(s):")
        for u, reason in failed:
            print(f"  ! {u} (ID: {u.id}) — {reason}")

    print("\n" + "=" * 50)
    total = len(added) + len(removed) + len(skipped) + len(failed)
    print(f"Total users processed: {total}")
    print("=" * 50 + "\n")


async def run(args):
    intents = discord.Intents.default()
    intents.members = True
    intents.reactions = True
    intents.guilds = True

    client = discord.Client(intents=intents)
    result_holder = {}

    @client.event
    async def on_ready():
        try:
            guild = client.get_guild(args.guild_id) or await client.fetch_guild(args.guild_id)
            print(f"Connected. Working in server: {guild.name} ({guild.id})")

            role = guild.get_role(args.role_id)
            if role is None:
                raise RuntimeError(f"Role {args.role_id} was not found in this server.")

            message = await find_message(guild, args.message_id, args.channel_id)
            print(f"Found target message (ID: {message.id}) in #{message.channel.name}")

            reaction_users = await collect_reaction_users(message, args.include_bots)
            poll_users = await collect_poll_voters(message, args.include_bots)

            all_users = {**reaction_users, **poll_users}
            print(
                f"Found {len(reaction_users)} reactor(s) and {len(poll_users)} poll voter(s) "
                f"({len(all_users)} unique user(s) total)."
            )

            if not all_users:
                print("No users found to process. Exiting.")
            else:
                added, removed, skipped, failed = await apply_role(
                    guild, all_users, role, args.action
                )
                log_results(added, removed, skipped, failed, args.action)

        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            await client.close()

    await client.start(TOKEN)


def main():
    if not TOKEN:
        print(
            "ERROR: DISCORD_TOKEN is not set. Create a .env file (see .env.example) "
            "or set the DISCORD_TOKEN environment variable."
        )
        sys.exit(1)

    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
