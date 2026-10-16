import pygame
from pathlib import Path

# Script lives at Pacman/Maze_runer.py, assets are at Pacman/assets/
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"



class GameEngine:

    def __init__(self) -> None:
        pygame.init()

        self.width, self.height = pygame.display.get_desktop_sizes()[0]
        self.screen = pygame.display.set_mode(
            (self.width, self.height), pygame.FULLSCREEN
        )
        pygame.display.set_caption("Pac-Man Basketball")

        self.clock = pygame.time.Clock()
        self.running = True

        # Load assets directly — no manager needed
        self.background_menu = self.load_image(
            "Midnight Arena Court with Open Center.png",
            size=(self.width, self.height),
        )
        pygame.display.flip()
    @staticmethod
    def load_image(filename, size=None, alpha=True):
        """Load an image from the assets folder, optionally scaled."""
        path = ASSETS_DIR / filename
        image = pygame.image.load(str(path))
        image = image.convert_alpha() if alpha else image.convert()
        if size is not None:
            image = pygame.transform.scale(image, size)
        return image
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    def run(self) -> None:
        self.screen.blit(self.background_menu, (0, 0))
        pygame.display.flip()

        while self.running:
            self.handle_events()
            self.screen.blit(self.background_menu, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    GameEngine().run()