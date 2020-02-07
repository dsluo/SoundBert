async def ok(ctx):
    await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')


async def warn(ctx):
    await ctx.message.add_reaction('\N{WARNING SIGN}')


async def err(ctx):
    await ctx.message.add_reaction('\N{NO ENTRY SIGN}')
