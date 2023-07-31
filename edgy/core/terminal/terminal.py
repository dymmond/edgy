from edgy.core.terminal.base import Base, OutputColour


class Terminal(Base):
    """Base output class for the terminal"""

    def write_success(
        self,
        message: str,
        colour: str = OutputColour.SUCCESS,
    ) -> str:
        """Outputs the successes to the console"""
        message = self.message(message, colour)
        return message

    def write_info(
        self,
        message: str,
        colour: str = OutputColour.INFO,
    ) -> str:
        """Outputs the info to the console"""
        message = self.message(message, colour)
        return message

    def write_warning(
        self,
        message: str,
        colour: str = OutputColour.WARNING,
    ) -> str:
        """Outputs the warnings to the console"""
        message = self.message(message, colour)
        return message

    def write_error(
        self,
        message: str,
        colour: str = OutputColour.ERROR,
    ) -> str:
        """Outputs the errors to the console"""
        message = self.message(message, colour)
        return message

    def write_plain(self, message: str, colour: str = OutputColour.WHITE) -> str:
        message = self.message(message, colour)
        return message
