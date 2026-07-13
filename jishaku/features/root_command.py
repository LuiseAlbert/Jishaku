import sys
import typing

try:
    from importlib.metadata import distribution, packages_distributions
except ImportError:
    from importlib_metadata import distribution, packages_distributions

import discord
from discord.ext import commands

from jishaku.features.baseclass import Feature
from jishaku.flags import Flags
from jishaku.math import natural_size
from jishaku.modules import package_version
from jishaku.paginators import PaginatorInterface
from jishaku.types import ContextA

try:
    import psutil
except ImportError:
    psutil = None


class RootCommand(Feature):

    def __init__(self, *args: typing.Any, **kwargs: typing.Any):
        super().__init__(*args, **kwargs)
        self.jsk.hidden = Flags.HIDE

    @Feature.Command(name="jishaku", aliases=["jsk","rex","eval","sahil", "nyn"],
                     invoke_without_command=True, ignore_extra=False)
    async def jsk(self, ctx: ContextA):
        distributions: typing.List[str] = [
            dist for dist in packages_distributions()['discord']
            if any(
                file.parts == ('discord', '__init__.py')
                for file in distribution(dist).files
            )
        ]

        if distributions:
            dist_version = f'{distributions[0]} `{package_version(distributions[0])}`'
        else:
            dist_version = f'unknown `{discord.__version__}`'

        summary = [
            f"Jishaku v{package_version('jishaku')}, {dist_version}, "
            f"`Python {sys.version}` on `{sys.platform}`".replace("\n", ""),
            f"Module was loaded <t:{self.load_time.timestamp():.0f}:R>, "
            f"cog was loaded <t:{self.start_time.timestamp():.0f}:R>.",
            ""
        ]

        if psutil:
            try:
                proc = psutil.Process()

                with proc.oneshot():
                    try:
                        mem = proc.memory_full_info()
                        summary.append(f"Using {natural_size(mem.rss)} physical memory and "
                                       f"{natural_size(mem.vms)} virtual memory, "
                                       f"{natural_size(mem.uss)} of which unique to this process.")
                    except psutil.AccessDenied:
                        pass

                    try:
                        name = proc.name()
                        pid = proc.pid
                        thread_count = proc.num_threads()

                        summary.append(f"Running on PID {pid} (`{name}`) with {thread_count} thread(s).")
                    except psutil.AccessDenied:
                        pass

                    summary.append("")
            except psutil.AccessDenied:
                summary.append(
                    "psutil is installed, but this process does not have high enough access rights "
                    "to query process information."
                )
                summary.append("")
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        s_for_guilds = "" if len(self.bot.guilds) == 1 else "s"
        s_for_users = "" if total_members == 1 else "s"
        cache_summary = f"{len(self.bot.guilds)} guild{s_for_guilds} and {total_members} user{s_for_users}"

        if isinstance(self.bot, discord.AutoShardedClient):
            if len(self.bot.shards) > 20:
                summary.append(
                    f"This bot is automatically sharded ({len(self.bot.shards)} shards of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
            else:
                shard_ids = ', '.join(str(i) for i in self.bot.shards.keys())
                summary.append(
                    f"This bot is automatically sharded (Shards {shard_ids} of {self.bot.shard_count})"
                    f" and can see {cache_summary}."
                )
        elif self.bot.shard_count:
            summary.append(
                f"This bot is manually sharded (Shard {self.bot.shard_id} of {self.bot.shard_count})"
                f" and can see {cache_summary}."
            )
        else:
            summary.append(f"This bot is not sharded and can see {cache_summary}.")

        if self.bot._connection.max_messages:
            message_cache = f"Message cache capped at {self.bot._connection.max_messages}"
        else:
            message_cache = "Message cache is disabled"

        remarks = {
            True: 'enabled',
            False: 'disabled',
            None: 'unknown'
        }

        *group, last = (
            f"{intent.replace('_', ' ')} intent is {remarks.get(getattr(self.bot.intents, intent, None))}"
            for intent in
            ('presences', 'members', 'message_content')
        )

        summary.append(f"{message_cache}, {', '.join(group)}, and {last}.")

        summary.append(f"**Average websocket latency:** **`{round(self.bot.latency * 1000, 2)}ms`**")
        rex = discord.Embed(
                description="\n".join(summary),
                color=0xAADBE2)
        rex.set_footer(text=f"made by itzmontage",
                             icon_url=self.bot.user.display_avatar.url)
        rex.set_thumbnail(url=self.bot.user.display_avatar.url)
        rex.set_author(name=ctx.author,icon_url=ctx.author.avatar.url
                if ctx.author.avatar else ctx.author.default_avatar.url)
        await ctx.send(embed=rex)
        
    @Feature.Command(parent="jsk", name="hide")
    async def jsk_hide(self, ctx: ContextA):

        if self.jsk.hidden:
            return await ctx.send("Jishaku is already hidden.")

        self.jsk.hidden = True
        await ctx.send("Jishaku is now hidden.")

    @Feature.Command(parent="jsk", name="show")
    async def jsk_show(self, ctx: ContextA):

        if not self.jsk.hidden:
            return await ctx.send("Jishaku is already visible.")

        self.jsk.hidden = False
        await ctx.send("Jishaku is now visible.")

    @Feature.Command(parent="jsk", name="tasks")
    async def jsk_tasks(self, ctx: ContextA):

        if not self.tasks:
            return await ctx.send("No currently running tasks.")

        paginator = commands.Paginator(max_size=1980)

        for task in self.tasks:
            if task.ctx.command:
                paginator.add_line(f"{task.index}: `{task.ctx.command.qualified_name}`, invoked at "
                                   f"{task.ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            else:
                paginator.add_line(f"{task.index}: unknown, invoked at "
                                   f"{task.ctx.message.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
        return await interface.send_to(ctx)

    @Feature.Command(parent="jsk", name="cancel")
    async def jsk_cancel(self, ctx: ContextA, *, index: typing.Union[int, str]):

        if not self.tasks:
            return await ctx.send("No tasks to cancel.")

        if index == "~":
            task_count = len(self.tasks)

            for task in self.tasks:
                if task.task:
                    task.task.cancel()

            self.tasks.clear()

            return await ctx.send(f"Cancelled {task_count} tasks.")

        if isinstance(index, str):
            raise commands.BadArgument('Literal for "index" not recognized.')

        if index == -1:
            task = self.tasks.pop()
        else:
            task = discord.utils.get(self.tasks, index=index)
            if task:
                self.tasks.remove(task)
            else:
                return await ctx.send("Unknown task.")

        if task.task:
            task.task.cancel()

        if task.ctx.command:
            await ctx.send(f"Cancelled task {task.index}: `{task.ctx.command.qualified_name}`,"
                           f" invoked {discord.utils.format_dt(task.ctx.message.created_at, 'R')}")
        else:
            await ctx.send(f"Cancelled task {task.index}: unknown,"
                           f" invoked {discord.utils.format_dt(task.ctx.message.created_at, 'R')}")
