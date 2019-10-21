from .soundboard import SoundBoard


def setup(bot):
    bot.add_cog(SoundBoard(bot))
