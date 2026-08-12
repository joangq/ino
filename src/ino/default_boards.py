from ino.board import Board

class ArduinoUno(Board):
    name = 'arduino:avr:uno'
    cpu = None

class ArduinoMega2560(Board):
    name = 'arduino:avr:mega'
    cpu = 'atmega2560'
