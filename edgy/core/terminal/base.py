from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from rich.console import Console

# Initialize a Rich Console object for beautiful terminal output.
console = Console()


class OutputColour(str, Enum):
    """
    Defines a comprehensive set of predefined color choices for terminal output.

    This Enum inherits from `str` to allow direct use of color names as string values,
    and from `Enum` to provide an enumerated set of options. It includes standard
    colors, as well as an extensive range of specific color codes for more granular
    control over terminal aesthetics, compatible with Rich's rendering capabilities.
    """

    # Standard success, info, warning, and error colors
    SUCCESS = "green"
    INFO = "cyan"
    WARNING = "yellow"
    ERROR = "red"

    # Basic colors
    WHITE = "white"
    MAGENTA = "magenta"
    BLUE = "blue"
    BLACK = "black"
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    CYAN = "cyan"

    # Bright variants of basic colors
    BRIGHT_BLACK = "bright_black"
    BRIGHT_RED = "bright_red"
    BRIGHT_GREEN = "bright_green"
    BRIGHT_YELLOW = "bright_yellow"
    BRIGHT_BLUE = "bright_blue"
    BRIGHT_MAGENTA = "bright_magenta"
    BRIGHT_CYAN = "bright_cyan"
    BRIGHT_WHITE = "bright_white"

    # Grayscale colors
    GREY0 = "grey0"
    GRAY0 = "gray0"  # Alias for grey0
    GREY3 = "grey3"
    GRAY3 = "gray3"  # Alias for grey3
    GREY7 = "grey7"
    GRAY7 = "gray7"  # Alias for grey7
    GREY11 = "grey11"
    GRAY11 = "gray11"  # Alias for grey11
    GREY15 = "grey15"
    GRAY15 = "gray15"  # Alias for grey15
    GREY19 = "grey19"
    GRAY19 = "gray19"  # Alias for grey19
    GREY23 = "grey23"
    GRAY23 = "gray23"  # Alias for grey23
    GREY27 = "grey27"
    GRAY27 = "gray27"  # Alias for grey27
    GREY30 = "grey30"
    GRAY30 = "gray30"  # Alias for grey30
    GREY35 = "grey35"
    GRAY35 = "gray35"  # Alias for grey35
    GREY37 = "grey37"
    GRAY37 = "gray37"  # Alias for grey37
    GREY39 = "grey39"
    GRAY39 = "gray39"  # Alias for grey39
    GREY42 = "grey42"
    GRAY42 = "gray42"  # Alias for grey42
    GREY46 = "grey46"
    GRAY46 = "gray46"  # Alias for grey46
    GREY50 = "grey50"
    GRAY50 = "gray50"  # Alias for grey50
    GREY53 = "grey53"
    GRAY53 = "gray53"  # Alias for grey53
    GREY54 = "grey54"
    GRAY54 = "gray54"  # Alias for grey54
    GREY58 = "grey58"
    GRAY58 = "gray58"  # Alias for grey58
    GREY62 = "grey62"
    GRAY62 = "gray62"  # Alias for grey62
    GREY63 = "grey63"
    GRAY63 = "gray63"  # Alias for grey63
    GREY66 = "grey66"
    GRAY66 = "gray66"  # Alias for grey66
    GREY69 = "grey69"
    GRAY69 = "gray69"  # Alias for grey69
    GREY70 = "grey70"
    GRAY70 = "gray70"  # Alias for grey70
    GREY74 = "grey74"
    GRAY74 = "gray74"  # Alias for grey74
    GREY78 = "grey78"
    GRAY78 = "gray78"  # Alias for grey78
    GREY82 = "grey82"
    GRAY82 = "gray82"  # Alias for grey82
    GREY84 = "grey84"
    GRAY84 = "gray84"  # Alias for grey84
    GREY85 = "grey85"
    GRAY85 = "gray85"  # Alias for grey85
    GREY89 = "grey89"
    GRAY89 = "gray89"  # Alias for grey89
    GREY93 = "grey93"
    GRAY93 = "gray93"  # Alias for grey93
    GREY100 = "grey100"
    GRAY100 = "gray100"  # Alias for grey100

    # Various shades of blue
    NAVY_BLUE = "navy_blue"
    DARK_BLUE = "dark_blue"
    BLUE3 = "blue3"
    BLUE1 = "blue1"
    DEEP_SKY_BLUE4 = "deep_sky_blue4"
    DODGER_BLUE3 = "dodger_blue3"
    DODGER_BLUE2 = "dodger_blue2"
    DEEP_SKY_BLUE3 = "deep_sky_blue3"
    DODGER_BLUE1 = "dodger_blue1"
    DEEP_SKY_BLUE2 = "deep_sky_blue2"
    DEEP_SKY_BLUE1 = "deep_sky_blue1"
    DARK_TURQUOISE = "dark_turquoise"
    TURQUOISE2 = "turquoise2"
    CADET_BLUE = "cadet_blue"
    SKY_BLUE3 = "sky_blue3"
    STEEL_BLUE1 = "steel_blue1"
    CORNFLOWER_BLUE = "cornflower_blue"
    LIGHT_SKY_BLUE3 = "light_sky_blue3"
    SKY_BLUE2 = "sky_blue2"
    SKY_BLUE1 = "sky_blue1"
    LIGHT_CYAN3 = "light_cyan3"
    LIGHT_SKY_BLUE1 = "light_sky_blue1"
    LIGHT_CYAN1 = "light_cyan1"
    STEEL_BLUE = "steel_blue"
    STEEL_BLUE3 = "steel_blue3"
    LIGHT_STEEL_BLUE3 = "light_steel_blue3"
    LIGHT_STEEL_BLUE = "light_steel_blue"
    LIGHT_STEEL_BLUE1 = "light_steel_blue1"
    ROYAL_BLUE1 = "royal_blue1"

    # Various shades of green
    DARK_GREEN = "dark_green"
    GREEN4 = "green4"
    SPRING_GREEN4 = "spring_green4"
    TURQUOISE4 = "turquoise4"
    GREEN3 = "green3"
    SPRING_GREEN3 = "spring_green3"
    DARK_CYAN = "dark_cyan"
    LIGHT_SEA_GREEN = "light_sea_green"
    SPRING_GREEN2 = "spring_green2"
    GREEN1 = "green1"
    SPRING_GREEN1 = "spring_green1"
    MEDIUM_SPRING_GREEN = "medium_spring_green"
    CYAN2 = "cyan2"
    CYAN1 = "cyan1"
    CHARTREUSE4 = "chartreuse4"
    DARK_SEA_GREEN4 = "dark_sea_green4"
    PALE_TURQUOISE4 = "pale_turquoise4"
    CHARTREUSE3 = "chartreuse3"
    PALE_GREEN3 = "pale_green3"
    SEA_GREEN3 = "sea_green3"
    AQUAMARINE3 = "aquamarine3"
    MEDIUM_TURQUOISE = "medium_turquoise"
    CHARTREUSE2 = "chartreuse2"
    SEA_GREEN2 = "sea_green2"
    SEA_GREEN1 = "sea_green1"
    AQUAMARINE1 = "aquamarine1"
    DARK_OLIVE_GREEN3 = "dark_olive_green3"
    DARK_SEA_GREEN = "dark_sea_green"
    DARK_SEA_GREEN3 = "dark_sea_green3"
    CHARTREUSE1 = "chartreuse1"
    LIGHT_GREEN = "light_green"
    PALE_GREEN1 = "pale_green1"
    GREEN_YELLOW = "green_yellow"
    DARK_OLIVE_GREEN2 = "dark_olive_green2"
    DARK_SEA_GREEN1 = "dark_sea_green1"
    HONEYDEW2 = "honeydew2"
    DARK_OLIVE_GREEN1 = "dark_olive_green1"
    DARK_SEA_GREEN2 = "dark_sea_green2"

    # Various shades of red/pink/magenta/purple
    DARK_RED = "dark_red"
    DEEP_PINK4 = "deep_pink4"
    PURPLE4 = "purple4"
    PURPLE3 = "purple3"
    BLUE_VIOLET = "blue_violet"
    MEDIUM_PURPLE4 = "medium_purple4"
    SLATE_BLUE3 = "slate_blue3"
    DARK_MAGENTA = "dark_magenta"
    DARK_VIOLET = "dark_violet"
    PURPLE = "purple"
    LIGHT_PINK4 = "light_pink4"
    PLUM4 = "plum4"
    MEDIUM_PURPLE3 = "medium_purple3"
    SLATE_BLUE1 = "slate_blue1"
    RED3 = "red3"
    MEDIUM_VIOLET_RED = "medium_violet_red"
    MAGENTA3 = "magenta3"
    INDIAN_RED = "indian_red"
    HOT_PINK3 = "hot_pink3"
    MEDIUM_ORCHID3 = "medium_orchid3"
    MEDIUM_ORCHID = "medium_orchid"
    MEDIUM_PURPLE2 = "medium_purple2"
    LIGHT_SALMON3 = "light_salmon3"
    ROSY_BROWN = "rosy_brown"
    MEDIUM_PURPLE1 = "medium_purple1"
    DEEP_PINK3 = "deep_pink3"
    MAGENTA2 = "magenta2"
    HOT_PINK2 = "hot_pink2"
    ORCHID = "orchid"
    MEDIUM_ORCHID1 = "medium_orchid1"
    LIGHT_PINK3 = "light_pink3"
    PINK3 = "pink3"
    PLUM3 = "plum3"
    VIOLET = "violet"
    MISTY_ROSE3 = "misty_rose3"
    THISTLE3 = "thistle3"
    PLUM2 = "plum2"
    DEEP_PINK2 = "deep_pink2"
    DEEP_PINK1 = "deep_pink1"
    MAGENTA1 = "magenta1"
    ORANGE_RED1 = "orange_red1"
    INDIAN_RED1 = "indian_red1"
    HOT_PINK = "hot_pink"
    SALMON1 = "salmon1"
    LIGHT_CORAL = "light_coral"
    PALE_VIOLET_RED1 = "pale_violet_red1"
    ORCHID2 = "orchid2"
    ORCHID1 = "orchid1"
    LIGHT_PINK1 = "light_pink1"
    PINK1 = "pink1"
    PLUM1 = "plum1"
    MISTY_ROSE1 = "misty_rose1"
    THISTLE1 = "thistle1"

    # Various shades of yellow/orange/brown
    ORANGE4 = "orange4"
    YELLOW4 = "yellow4"
    WHEAT4 = "wheat4"
    DARK_GOLDENROD = "dark_goldenrod"
    GOLD3 = "gold3"
    DARK_KHAKI = "dark_khaki"
    NAVAJO_WHITE3 = "navajo_white3"
    YELLOW3 = "yellow3"
    LIGHT_GOLDENROD3 = "light_goldenro_d3"
    TAN = "tan"
    KHAKI3 = "khaki3"
    LIGHT_GOLDENROD2 = "light_goldenrod2"
    LIGHT_YELLOW3 = "light_yellow3"
    YELLOW2 = "yellow2"
    DARK_ORANGE3 = "dark_orange3"
    ORANGE3 = "orange3"
    LIGHT_GOLDENROD1 = "light_goldenrod1"
    KHAKI1 = "khaki1"
    WHEAT1 = "wheat1"
    CORNSILK1 = "cornsilk1"
    ORANGE1 = "orange1"
    SANDY_BROWN = "sandy_brown"
    LIGHT_SALMON1 = "light_salmon1"
    GOLD1 = "gold1"
    NAVAJO_WHITE1 = "navajo_white1"
    YELLOW1 = "yellow1"
    DARK_ORANGE = "dark_orange"

    # Dark slate colors
    DARK_SLATE_GRAY2 = "dark_slate_gray2"
    DARK_SLATE_GRAY3 = "dark_slate_gray3"
    DARK_SLATE_GRAY1 = "dark_slate_gray1"

    def __str__(self) -> str:
        """
        Returns the string value of the enum member, which represents the color name.
        """
        return self.value

    def __repr__(self) -> str:
        """
        Returns a string representation of the enum member, identical to its string value.
        This makes debugging and display more intuitive as it directly shows the color name.
        """
        return str(self)


class Base(ABC, Console):
    """
    Abstract base class for terminal output operations.

    This class extends `rich.console.Console` and defines an interface for various
    types of terminal messages, enforcing consistency across different output
    implementations. Each abstract method corresponds to a specific message
    type (success, info, warning, error) with a default color.
    """

    @abstractmethod
    def write_success(self, message: str, colour: str = OutputColour.SUCCESS) -> str | None:
        """
        Abstract method to write a success message to the console.

        Implementations should provide the logic for displaying success messages,
        typically in green.

        Parameters:
            message (str): The content of the success message.
            colour (str): The color to use for the message. Defaults to `OutputColour.SUCCESS`.

        Returns:
            str | None: The formatted message string, or None if direct printing is handled.
        """
        raise NotImplementedError()

    @abstractmethod
    def write_info(self, message: str, colour: str = OutputColour.INFO) -> str | None:
        """
        Abstract method to write an informational message to the console.

        Implementations should provide the logic for displaying informational messages,
        typically in cyan.

        Parameters:
            message (str): The content of the informational message.
            colour (str): The color to use for the message. Defaults to `OutputColour.INFO`.

        Returns:
            str | None: The formatted message string, or None if direct printing is handled.
        """
        raise NotImplementedError()

    @abstractmethod
    def write_warning(self, message: str, colour: str = OutputColour.WARNING) -> str | None:
        """
        Abstract method to write a warning message to the console.

        Implementations should provide the logic for displaying warning messages,
        typically in yellow.

        Parameters:
            message (str): The content of the warning message.
            colour (str): The color to use for the message. Defaults to `OutputColour.WARNING`.

        Returns:
            str | None: The formatted message string, or None if direct printing is handled.
        """
        # This method is abstract and must be implemented by concrete subclasses.
        raise NotImplementedError()

    @abstractmethod
    def write_error(self, message: str, colour: str = OutputColour.ERROR) -> str | None:
        """
        Abstract method to write an error message to the console.

        Implementations should provide the logic for displaying error messages,
        typically in red.

        Parameters:
            message (str): The content of the error message.
            colour (str): The color to use for the message. Defaults to `OutputColour.ERROR`.

        Returns:
            str | None: The formatted message string, or None if direct printing is handled.
        """
        raise NotImplementedError()

    def write_plain(self, message: str, colour: str = OutputColour.WHITE) -> str | None:
        """
        Writes a plain message to the console with a custom color.

        This is a concrete method providing a default implementation for writing
        messages that don't fit into the predefined success, info, warning, or error
        categories, defaulting to white. Subclasses can override this if needed.

        Parameters:
            message (str): The content of the plain message.
            colour (str): The color to use for the message. Defaults to `OutputColour.WHITE`.

        Returns:
            str | None: The formatted message string, or None if direct printing is handled.
        """
        raise NotImplementedError()

    def write(self, message: Any) -> None:
        """
        Prints any given message to the console using the underlying Rich `print` method.

        This method acts as a direct passthrough to the Rich Console's printing
        functionality, allowing for flexible output of various data types.

        Parameters:
            message (Any): The message content to be printed. This can be a string,
                           Rich Renderable, or any object that `rich.console.Console.print`
                           can handle.
        """
        self.print(message)

    def message(self, message: str, colour: str) -> str:
        """
        Formats a message string with Rich-compatible color tags.

        This utility method encapsulates the creation of a colored string
        that can be rendered by Rich. It does not print the message but
        returns the formatted string.

        Parameters:
            message (str): The raw message string to be colored.
            colour (str): The name of the color to apply (e.g., "red", "green", "blue").

        Returns:
            str: The message string wrapped with Rich color tags (e.g., "[red]my message[/red]").
        """
        return f"[{colour}]{message}[/{colour}]"
