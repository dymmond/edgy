from edgy.core.terminal.base import Base, OutputColour


class Print(Base):
    """
    Provides concrete implementations for printing various types of messages to the terminal.

    This class inherits from `Base` and fulfills the abstract methods defined there,
    using Rich's `console.print` to display colored output. It serves as the primary
    utility for consistent message display across the application's command-line interface.
    """

    def write_success(self, message: str, colour: str = OutputColour.SUCCESS) -> None:
        """
        Writes a success message to the console, typically in green.

        This method formats the input `message` with the specified `colour` (defaulting
        to `OutputColour.SUCCESS`) and then prints it to the console using Rich.

        Parameters:
            message (str): The content of the success message.
            colour (str): The color to use for the message. Defaults to `OutputColour.SUCCESS`.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Print the formatted message to the console.
        self.print(message)

    def write_info(self, message: str, colour: str = OutputColour.INFO) -> None:
        """
        Writes an informational message to the console, typically in cyan.

        This method formats the input `message` with the specified `colour` (defaulting
        to `OutputColour.INFO`) and then prints it to the console using Rich.

        Parameters:
            message (str): The content of the informational message.
            colour (str): The color to use for the message. Defaults to `OutputColour.INFO`.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Print the formatted message to the console.
        self.print(message)

    def write_warning(self, message: str, colour: str = OutputColour.WARNING) -> None:
        """
        Writes a warning message to the console, typically in yellow.

        This method formats the input `message` with the specified `colour` (defaulting
        to `OutputColour.WARNING`) and then prints it to the console using Rich.

        Parameters:
            message (str): The content of the warning message.
            colour (str): The color to use for the message. Defaults to `OutputColour.WARNING`.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Print the formatted message to the console.
        self.print(message)

    def write_plain(self, message: str, colour: str = OutputColour.WHITE) -> None:
        """
        Writes a plain message to the console with a custom color, defaulting to white.

        This method formats the input `message` with the specified `colour` (defaulting
        to `OutputColour.WHITE`) and then prints it to the console using Rich. It's
        suitable for general output that doesn't fit into the predefined categories.

        Parameters:
            message (str): The content of the plain message.
            colour (str): The color to use for the message. Defaults to `OutputColour.WHITE`.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Print the formatted message to the console.
        self.print(message)

    def write_error(self, message: str, colour: str = OutputColour.ERROR) -> None:
        """
        Writes an error message to the console, typically in red.

        This method formats the input `message` with the specified `colour` (defaulting
        to `OutputColour.ERROR`) and then prints it to the console using Rich.

        Parameters:
            message (str): The content of the error message.
            colour (str): The color to use for the message. Defaults to `OutputColour.ERROR`.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Print the formatted message to the console.
        self.print(message)
