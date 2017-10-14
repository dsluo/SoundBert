# Adds checkmark emoji to ctx message
async def yes(ctx):
    await ctx.message.add_reaction('\U00002705')


# Adds cancel sign emoji to ctx message
async def no(ctx):
    await ctx.message.add_reaction('\U0001f6ab')
