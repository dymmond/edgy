from edgy.core.terminal.base import Base, OutputColour


class Terminal(Base):
    """
    Provides methods for formatting terminal output messages with specific colors.

    Unlike the `Print` class, this class does not directly print to the console.
    Instead, its `write_*` methods return the formatted string, allowing the caller
    to decide how and when to display the output. This makes it suitable for
    scenarios where messages need to be captured, logged, or further processed
    before being sent to standard output.
    """

    def write_success(self, message: str, colour: str = OutputColour.SUCCESS) -> str:
        """
        Formats a success message with the specified color, typically green.

        This method generates a Rich-compatible string with color tags but does not
        print it to the console. The returned string can then be printed by
        another function or stored.

        Parameters:
            message (str): The content of the success message.
            colour (str): The color to use for the message. Defaults to `OutputColour.SUCCESS`.

        Returns:
            str: The formatted message string with Rich color tags.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Return the formatted message.
        return message

    def write_info(self, message: str, colour: str = OutputColour.INFO) -> str:
        """
        Formats an informational message with the specified color, typically cyan.

        This method generates a Rich-compatible string with color tags but does not
        print it to the console. The returned string can then be printed by
        another function or stored.

        Parameters:
            message (str): The content of the informational message.
            colour (str): The color to use for the message. Defaults to `OutputColour.INFO`.

        Returns:
            str: The formatted message string with Rich color tags.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Return the formatted message.
        return message

    def write_warning(self, message: str, colour: str = OutputColour.WARNING) -> str:
        """
        Formats a warning message with the specified color, typically yellow.

        This method generates a Rich-compatible string with color tags but does not
        print it to the console. The returned string can then be printed by
        another function or stored.

        Parameters:
            message (str): The content of the warning message.
            colour (str): The color to use for the message. Defaults to `OutputColour.WARNING`.

        Returns:
            str: The formatted message string with Rich color tags.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Return the formatted message.
        return message

    def write_error(self, message: str, colour: str = OutputColour.ERROR) -> str:
        """
        Formats an error message with the specified color, typically red.

        This method generates a Rich-compatible string with color tags but does not
        print it to the console. The returned string can then be printed by
        another function or stored.

        Parameters:
            message (str): The content of the error message.
            colour (str): The color to use for the message. Defaults to `OutputColour.ERROR`.

        Returns:
            str: The formatted message string with Rich color tags.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Return the formatted message.
        return message

    def write_plain(self, message: str, colour: str = OutputColour.WHITE) -> str:
        """
        Formats a plain message with the specified custom color, defaulting to white.

        This method generates a Rich-compatible string with color tags but does not
        print it to the console. The returned string can then be printed by
        another function or stored. It's suitable for general output that doesn't
        fit into the predefined success, info, warning, or error categories.

        Parameters:
            message (str): The content of the plain message.
            colour (str): The color to use for the message. Defaults to `OutputColour.WHITE`.

        Returns:
            str: The formatted message string with Rich color tags.
        """
        # Format the message with Rich color tags.
        message = self.message(message, colour)
        # Return the formatted message.
        return message
