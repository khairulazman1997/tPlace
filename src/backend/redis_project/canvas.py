from commons import *
from logging import getLogger, StreamHandler
import redis


logger = getLogger()


def format_offset(pixel_offset: int) -> str:
    """
    Formats an offset string into its required Redis format.
    :param pixel_offset: The integer offset value required.
    :return: Returns the formatted string.
    """
    return ''.join(['#', str(pixel_offset)])


def calculate_offset(pixel_x_coordinate: int, pixel_y_coordinate: int, canvas_width: int) -> str:
    """
    Calculates the required offset of the chosen pixel, given the x and y coordinates of the pixel. Both coordinates
    must be entered in 1-indexed form (i.e. smallest coordinate value is 1, not 0).
    :param pixel_x_coordinate: The x-coordinate of the pixel, 1-indexed.
    :param pixel_y_coordinate: The y-coordinate of the pixel, 1-indexed.
    :param canvas_width: The width of the canvas, in pixels.
    :return: Returns a formatted offset string for use in Redis.
    """
    height_index_offset = convert_one_index_to_zero_index(pixel_y_coordinate) * canvas_width
    width_index_offset = convert_one_index_to_zero_index(pixel_x_coordinate)
    offset = format_offset(height_index_offset + width_index_offset)
    return offset


class Canvas:
    """
    Represents a Canvas object. The canvas itself is stored as a bitfield on a Redis server. Each pixel on the canvas
    has a color that is represented by its value. Supported functions are getter and setter functions for pixels, and
    a getter function for the whole bitfield.
    """
    width: int = None
    height: int = None
    name: str = None
    pixel_format: str = None
    database = None

    def __init__(self, width, height, pixel_format, name, host, port):
        """
        Initializes the Canvas object.
        :param width: The width of the canvas, in pixels.
        :param height: The height of the canvas, in pixels.
        :param pixel_format: The number of bits in a pixel.
        :param name: The name of the canvas when stored in the database.
        :param host: The host address for the Redis server used as the database.
        :param port: The port number for the Redis server used as the database.
        """
        self.width = width
        self.height = height
        self.name = name
        self.pixel_format = pixel_format
        self.database = redis.Redis(host=host, port=port)
        self._fill_with_white_pixels()

    def get_pixel_color(self, pixel_x_coordinate: int, pixel_y_coordinate: int) -> int:
        """
        Gets the integer value of a pixel, given its x and y coordinates. The coordinates must be 1-indexed (i.e. the
        smallest value is 1, not 0).
        :param pixel_x_coordinate: The x-coordinate of the pixel, which must be 1-indexed.
        :param pixel_y_coordinate: The y-coordinate of the pixel, which must be 1-indexed.
        :return: Returns the integer value of the pixel.
        """
        offset = calculate_offset(pixel_x_coordinate, pixel_y_coordinate, self.width)
        pixel_value = self.database.bitfield(key=self.name).get(fmt=self.pixel_format, offset=offset).execute()
        logger.info("Getting pixel color at offset {}: color {}".format(offset, pixel_value))
        return pixel_value

    def set_pixel_color(self, pixel_x_coordinate: int, pixel_y_coordinate: int, color: Color) -> None:
        """
        Sets a pixel color, given its x and y coordinates and new color. The coordinates must be 1-indexed (i.e. the
        smallest value is 1, not 0).
        :param pixel_x_coordinate: The x-coordinate of the pixel, which must be 1-indexed.
        :param pixel_y_coordinate: The y-coordinate of the pixel, which must be 1-indexed.
        :param color: The intended color of the pixel, which must be from the Color class.
        """
        offset = calculate_offset(pixel_x_coordinate, pixel_y_coordinate, self.width)
        logger.info("Setting pixel color at offset {} to color {}".format(offset, color.value))
        self.database.bitfield(key=self.name).set(fmt=self.pixel_format, offset=offset, value=color.value).execute()

    def set_pixel_region(self, top_left_pixel_x_coordinate: int, top_left_pixel_y_coordinate: int,
                         bottom_right_pixel_x_coordinate: int, bottom_right_pixel_y_coordinate: int) -> None:
        """
        Sets a region of pixels to the default color (white). The x and y coordinates of the top-left and bottom-right
        corners must be specified. This method will then set the entire rectangular region within the corners to the
        default color, inclusive of both corners.
        :param top_left_pixel_x_coordinate: x-coordinate of the top-left corner.
        :param top_left_pixel_y_coordinate: y-coordinate of the top-left corner.
        :param bottom_right_pixel_x_coordinate: x-coordinate of the bottom-right corner.
        :param bottom_right_pixel_y_coordinate: y-coordinate of the bottom-right corner.
        """
        # width_of_region = bottom_right_pixel_x_coordinate - top_left_pixel_x_coordinate + 1
        # row_value = "0000" * width_of_region
        for y_coordinate in range(top_left_pixel_y_coordinate, bottom_right_pixel_y_coordinate + 1):
            # offset = calculate_offset(top_left_pixel_x_coordinate, y_coordinate, self.width)
            # logger.warning("Offset: {}, Row: {}".format(offset, row_value))
            # self.database.setrange(name=self.name, offset=offset, value=).execute()
            for x_coordinate in range(top_left_pixel_x_coordinate, bottom_right_pixel_x_coordinate + 1):
                offset = calculate_offset(x_coordinate, y_coordinate, self.width)
                self.database.bitfield(key=self.name).set(fmt=self.pixel_format, offset=offset,
                                                          value=Color.WHITE.value).execute()

    def get_canvas(self) -> bytes:
        """
        Returns the entire stored canvas bitfield as one long stream of bytes. When converted to a string, the bytes
        may look strange or unusual; however, they are present.
        :return: Returns the canvas bitfield as bytes.
        """
        bitfield = self.database.get(name=self.name)
        logger.info("Requested entire board: {}".format(str(bitfield)))
        return bitfield

    def to_string(self) -> str:
        """
        Returns a visual representation of the bitfield as a string. The rows and columns of the bitfield will be shown
        correctly. This should only be used for debugging.
        :return: Returns a representation of the canvas bitfield as a string.
        """
        bitfield_string = ""
        for y_coordinate in range(self.height):
            for x_coordinate in range(self.width):
                offset = calculate_offset(x_coordinate + 1, y_coordinate + 1, self.width)
                logger.debug("Printing pixel at offset {}".format(offset))
                next_pixel_value = self.database.bitfield(key=self.name).get(fmt=self.pixel_format, offset=offset)\
                    .execute()
                bitfield_string = "".join([bitfield_string, str(next_pixel_value)])
            bitfield_string = "".join([bitfield_string, "\n"])
        return bitfield_string

    def _fill_with_white_pixels(self) -> None:
        """
        Initializes all pixel values on the canvas with zeroes. The number of pixels initialized is exactly the number
        of pixels that would fit in a canvas of the width and height used as parameters for the construction of this
        Canvas object.
        """
        self.set_pixel_region(1, 1, CANVAS_WIDTH, CANVAS_HEIGHT)


if __name__ == "__main__":
    logger.addHandler(StreamHandler())
    # logger.setLevel(level="INFO")
    # logger.setLevel(level="DEBUG")

    canvas = Canvas(width=CANVAS_WIDTH, height=CANVAS_HEIGHT, pixel_format=PIXEL_FORMAT, name=CANVAS_NAME,
                    host=REDIS_HOST_ADDRESS, port=REDIS_HOST_PORT)
    # canvas.get_canvas()
    print(canvas.to_string())
    for i in range(CANVAS_HEIGHT):
        for j in range(CANVAS_WIDTH):
            canvas.set_pixel_color(j + 1, i + 1, Color.GREY)
    print(canvas.to_string())
    # canvas.get_canvas()
    try:
        canvas.set_pixel_region(2, 2, 4, 4)
        print("Completed")
    except Exception as e:
        print(e)
    print(canvas.to_string())
    # canvas.get_canvas()
