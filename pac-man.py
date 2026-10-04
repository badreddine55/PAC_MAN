from parsing import Parser

class Game_ingen:
    def __init__(self):
        pass
    def _load_data(self):
        parser_data = Parser()
        dict_data:dict = parser_data._load_json("config.json")
        print(parser_data._parsing_dict(dict_data))


if __name__ == "__main__":
    game = Game_ingen()
    game._load_data()