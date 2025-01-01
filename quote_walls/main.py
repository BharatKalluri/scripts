from PIL import Image, ImageDraw, ImageFont
import textwrap
import subprocess
from pathlib import Path
import random
import time
import os

DEFAULT_QUOTES = [
    "And those who were seen dancing were thought to be insane by those who could not hear the music - Nietzsche",
    "We buy things we don't need with money we don't have to impress people we don't like - Chuck Palahniuk",
    "Ships are safe at the harbour, but that's not what they are built for - Anonymous",
    "If someone could only see your actions but not hear your words, what would they say your priorities are? - Anonymous",
    "Hard times create strong men. Strong men create good times. Good times create weak men. And, weak men create hard times - G. Michael Hopf",
]


def generate_wallpaper(
    quote: str,
    width: int = 3440,
    height: int = 1440,
    background_color: str = "#C73B13",
    text_color: str = "#020003",
) -> bytes:
    """Generate a wallpaper with the given quote and author and return the image as bytes.

    Args:
        quote: The quote text in format "quote - author"
        width: Width of the wallpaper in pixels
        height: Height of the wallpaper in pixels
        background_color: Hex color code for background
        text_color: Hex color code for text
    """
    quote, author = [s.strip() for s in quote.split("-")]

    # Create image
    img = Image.new("RGB", (width, height), background_color)
    draw = ImageDraw.Draw(img)

    # Load serif font with size at least 8% of height
    font_path = Path(__file__).parent / "CrimsonText-SemiBold.ttf"
    font_for_quote = ImageFont.truetype(str(font_path), size=int(height * 0.08))

    # Set padding
    padding = 100

    # Wrap text to fit within padding
    wrapper = textwrap.TextWrapper(
        width=30, break_long_words=False
    )  # Adjusted for larger font
    wrapped_lines = wrapper.wrap(quote)

    # Join lines with newlines
    wrapped_quote = "\n".join(wrapped_lines)

    # Calculate text dimensions
    quote_bbox = draw.textbbox((0, 0), wrapped_quote, font=font_for_quote)
    quote_height = quote_bbox[3] - quote_bbox[1]

    quote_x = padding  # Left align with padding
    quote_y = (
        height - quote_height
    ) // 2 - 50  # Vertically centered, shifted up for author

    # Draw quote
    draw.text((quote_x, quote_y), wrapped_quote, font=font_for_quote, fill=text_color)

    # Draw author
    author_text = f"- {author}"
    author_lines = wrapper.wrap(author_text)
    author = "\n".join(author_lines)
    author_y = quote_y + quote_height + 30
    draw.text((quote_x, author_y), author, font=font_for_quote, fill=text_color)

    # Convert image to bytes
    from io import BytesIO

    img_byte_arr = BytesIO()
    img.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def set_wallpaper(wallpaper_bytes: bytes) -> None:
    """Set the wallpaper on GNOME desktop using the provided image bytes."""
    # Save bytes to temporary file
    temp_path = Path.home() / ".cache" / "current_wallpaper.png"
    temp_path.parent.mkdir(parents=True, exist_ok=True)

    with open(temp_path, "wb") as f:
        f.write(wallpaper_bytes)

    # Set as wallpaper using gsettings
    subprocess.run(
        [
            "gsettings",
            "set",
            "org.gnome.desktop.background",
            "picture-uri-dark",
            f"file://{temp_path}",
        ]
    )
    subprocess.run(
        [
            "gsettings",
            "set",
            "org.gnome.desktop.background",
            "picture-uri",
            f"file://{temp_path}",
        ]
    )


def main():
    # Seed random with system entropy
    random.seed(int.from_bytes(os.urandom(8), byteorder="big") ^ int(time.time() * 1000))
    
    # Generate wallpaper for random quote
    quote = random.choice(DEFAULT_QUOTES)
    wallpaper_bytes = generate_wallpaper(
        quote=quote,
        width=3440,
        height=1440,
        background_color="#C73B13",
        text_color="#020003",
    )

    # Set as wallpaper
    set_wallpaper(wallpaper_bytes)
    print("Wallpaper has been set")


if __name__ == "__main__":
    main()
