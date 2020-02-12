import abc
import asyncio
from collections import OrderedDict
from typing import List

import discord
from discord import User, Reaction, Message
from discord.ext import commands

FIRST = '\N{BLACK LEFT-POINTING DOUBLE TRIANGLE}'
PREV = '\N{BLACK LEFT-POINTING TRIANGLE}'
NEXT = '\N{BLACK RIGHT-POINTING TRIANGLE}'
LAST = '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}'


class Paginator(abc.ABC):
    def __init__(
            self,
            ctx: commands.Context,
            items: List[str],
            timeout=120,
            header='',
            enumerate=True):
        self.ctx = ctx
        self.items = items
        self.timeout = timeout
        self.header = header.strip()
        self.enumerate = enumerate

        self._pages = None

        self.page = 0
        self.page_count = len(self.pages)

        self.paginating = False
        self.msg: Message = None
        self.reactions = {
            FIRST: self.first,
            PREV:  self.prev,
            NEXT:  self.next,
            LAST:  self.last
        }

    @property
    def pages(self) -> List[str]:
        if self._pages is not None:
            return self._pages

        self._pages = []

        if not self.items:
            return self._pages

        self._pages = self._gen_pages()

        return self._pages

    @abc.abstractmethod
    def _gen_pages(self) -> List[str]:
        pass

    def _check(self, reaction: Reaction, user: User):
        if reaction.message.id != self.msg.id:
            return False
        if user.bot:
            return False
        if reaction.emoji not in self.reactions.keys():
            return False
        return True

    async def _setup(self):
        await self.first()

        for reaction in self.reactions:
            await self.msg.add_reaction(reaction)
        self.paginating = True

    async def _teardown(self):
        await self.msg.clear_reactions()
        self.paginating = False

    async def paginate(self):
        await self._setup()

        while self.paginating:
            try:
                reaction, user = await self.ctx.bot.wait_for('reaction_add', check=self._check, timeout=self.timeout)

                try:
                    await reaction.remove(user)
                except discord.HTTPException:
                    pass

                action = self.reactions[reaction.emoji]
                await action()
            except asyncio.TimeoutError:
                await self._teardown()
                break

    async def first(self):
        await self.goto(0)

    async def prev(self):
        await self.goto(self.page - 1)

    async def next(self):
        await self.goto(self.page + 1)

    async def last(self):
        await self.goto(self.page_count - 1)

    async def goto(self, page: int):
        if not (0 <= page < self.page_count):
            return

        page_contents = self.pages[page]

        if self.msg is None:
            self.msg = await self.ctx.send(str(page_contents))
        else:
            await self.msg.edit(content=str(page_contents))

        self.page = page


class DictionaryPaginator(Paginator):
    def _gen_pages(self) -> List[str]:
        if not self.items:
            return [f'**{self.header}**\nThere is nothing here.']

        split = OrderedDict()
        for item in sorted(self.items):
            try:
                first = item[0].lower()
                if first not in 'abcdefghijklmnopqrstuvwxyz':
                    first = '#'
            except IndexError:
                first = '#'
            if first not in split.keys():
                split[first] = [item]
            else:
                split[first].append(item)

        # worst case 1 item per page
        page_digits = len(str(len(self.items)))


        header = f'{self.header}\n' if self.header else ''

        footer_fmt = "\nPage {page_no}/{page_count}"
        footer_placeholder = footer_fmt.format(page_no='*' * page_digits, page_count='*' * page_digits)
        footer_len = len(footer_placeholder)

        char_count = len(header)
        page = [header]
        pages = []

        for key, items in split.items():
            # if adding a key is too long for one message, new page.
            key = f'**{key}**: '
            if char_count + len(key) + footer_len + 1 > 2000:
                pages.append(page)
                page = [header]
                char_count = len(header)

            page.append(key)
            char_count += len(key)

            for item in items:
                item = f'{item} '
                # 1 for newline at end of section
                if char_count + len(item) + footer_len + 1 > 2000:
                    pages.append(page)
                    page = [header, key]
                    char_count = len(header) + len(key)

                page.append(item)
                char_count += len(item)

            page.append('\n')
        if page:
            pages.append(page)

        for i, page in enumerate(pages):
            page.append(footer_fmt.format(page_no=i + 1, page_count=len(pages)))

        pages = [''.join(page) for page in pages]

        return pages

