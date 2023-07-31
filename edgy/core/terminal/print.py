from edgy.core.terminal.base import Base, OutputColour


class Print(Base):
    """Base output class for the terminal"""

    def write_success(
        self,
        message: str,
        colour: str = OutputColour.SUCCESS,
    ) -> None:
        """Outputs the successes to the console"""
        message = self.message(message, colour)
        self.print(message)

    def write_info(self, message: str, colour: str = OutputColour.INFO) -> None:
        """Outputs the info to the console"""
        message = self.message(message, colour)
        self.print(message)

    def write_warning(
        self,
        message: str,
        colour: str = OutputColour.WARNING,
    ) -> None:
        """Outputs the warnings to the console"""
        message = self.message(message, colour)
        self.print(message)

    def write_plain(self, message: str, colour: str = OutputColour.WHITE) -> None:
        message = self.message(message, colour)
        self.print(message)

    def write_error(
        self,
        message: str,
        colour: str = OutputColour.ERROR,
    ) -> None:
        """Outputs the errors to the console"""
        message = self.message(message, colour)
        self.print(message)
