from typing import Callable

from Console import Console


#
#   A console handler that produces output by simply printing it to standard output
#
class ConsoleSimplePrint(Console):

    def __init__(self):
        Console.__init__(self)

    def output_message(self, message: str):
        print(message)