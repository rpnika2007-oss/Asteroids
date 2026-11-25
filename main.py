"""Точка входа, игровой цикл и состояния космической аркады."""

from enum import Enum, auto
from math import ceil
from random import choice, uniform

import pygame
from pygame.math import Vector2

import settings as cfg
from effects import Background, Explosion, load_image
from entities import Asteroid, Rocket, Ship, torus_distance_squared


class State(Enum):
    """Состояния начального экрана, партии и экрана результата."""

    MENU = auto()
    PLAYING = auto()
    GAME_OVER = auto()


class Game:
    """Управляет вводом, физикой, столкновениями и отрисовкой."""

    def __init__(self) -> None:
        """Создаёт окно, загружает изображения и открывает заставку."""
        self.screen = pygame.display.set_mode(cfg.SCREEN_SIZE)
        pygame.display.set_caption(cfg.WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.background = Background()
        self.ship_idle = load_image("ship.png")
        self.ship_thrust = load_image("ship_thrust.png")
        self.rocket_image = load_image("rocket.png")
        self.asteroid_types = [
            (load_image(name), radius) for name, radius in cfg.ASTEROID_TYPES
        ]
        self.explosion_frames = Explosion.load_frames()

        self.label_font = pygame.font.SysFont(cfg.UI_FONT, cfg.UI_SMALL_FONT)
        self.value_font = pygame.font.SysFont(
            cfg.UI_FONT, cfg.UI_VALUE_FONT, bold=True
        )
        title_font = pygame.font.SysFont(
            cfg.UI_FONT, cfg.UI_TITLE_SIZE, bold=True
        )
        self.title = title_font.render("ASTEROIDS", True, cfg.UI_TEXT)
        pygame.display.set_icon(self.ship_idle)
        self.card = pygame.Rect((0, 0), cfg.UI_CARD_SIZE)
        self.card.center = cfg.SCREEN_CENTER
        self.card_panel = pygame.Surface(cfg.UI_CARD_SIZE, pygame.SRCALPHA)
        pygame.draw.rect(
            self.card_panel, cfg.UI_PANEL, self.card_panel.get_rect(),
            border_radius=cfg.UI_CARD_RADIUS,
        )

        self.running = True
        self.state = State.MENU
        self.lives = cfg.START_LIVES
        self.score = 0
        self.spawn_timer = cfg.SPAWN_INTERVAL
        self.ship: Ship | None = None
        self.asteroids: list[Asteroid] = []
        self.rockets: list[Rocket] = []
        self.explosions: list[Explosion] = []

    def start(self) -> None:
        """Сбрасывает счёт и создаёт объекты новой партии."""
        self._clear_field()
        self.explosions.clear()
        self.lives = cfg.START_LIVES
        self.score = 0
        self.spawn_timer = cfg.SPAWN_INTERVAL
        self.ship = Ship(self.ship_idle, self.ship_thrust)
        for _ in range(cfg.INITIAL_ASTEROIDS):
            self._spawn_asteroid(self.ship)
        self.state = State.PLAYING

    def _clear_field(self) -> None:
        """Освободить поле от корабля, астероидов и ракет."""
        self.ship = None
        self.asteroids.clear()
        self.rockets.clear()

    def _spawn_asteroid(self, ship: Ship) -> None:
        """Создать астероид на безопасном расстоянии от корабля."""
        image, radius = choice(self.asteroid_types)
        clearance = ship.radius + radius + cfg.SPAWN_CLEARANCE
        while True:
            position = Vector2(
                uniform(0, cfg.SCREEN_WIDTH), uniform(0, cfg.SCREEN_HEIGHT)
            )
            if torus_distance_squared(position, ship.position) > clearance**2:
                self.asteroids.append(Asteroid(position, image, radius))
                return

    def handle_event(self, event: pygame.event.Event) -> None:
        """Обработать выход, щелчок по заставке и выстрел."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.running = False
        elif self.state is State.PLAYING:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if self.ship is not None:
                    rocket = self.ship.fire(self.rocket_image)
                    if rocket is not None:
                        self.rockets.append(rocket)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.card.collidepoint(event.pos):
                self.start()

    def _destroy_asteroid(self, asteroid: Asteroid) -> None:
        """Удаляет астероид и создаёт самостоятельный эффект взрыва."""
        self.asteroids.remove(asteroid)
        self.explosions.append(
            Explosion(asteroid.position, self.explosion_frames)
        )

    def _resolve_collisions(self, ship: Ship) -> None:
        """Разрешить попадания ракет перед столкновением корабля.

        Удалённый астероид сразу перестаёт участвовать в проверках.
        При завершении партии на экране остаётся только последний взрыв.
        """
        for rocket in self.rockets[:]:
            for asteroid in self.asteroids:
                if rocket.touches(asteroid):
                    self.rockets.remove(rocket)
                    self._destroy_asteroid(asteroid)
                    self.score += 1
                    break

        if ship.protection > cfg.TIME_EPSILON:
            return
        for asteroid in self.asteroids:
            if ship.touches(asteroid):
                if self.lives == 0:
                    self.explosions.clear()
                self._destroy_asteroid(asteroid)
                if self.lives > 0:
                    self.lives -= 1
                    ship.respawn()
                else:
                    self.state = State.GAME_OVER
                    self._clear_field()
                break

    def _step(self, dt: float, ship: Ship) -> None:
        """Продвигает объекты и таймеры на один малый шаг физики."""
        self.spawn_timer -= dt
        if self.spawn_timer <= cfg.TIME_EPSILON:
            self.spawn_timer += cfg.SPAWN_INTERVAL
            if len(self.asteroids) < cfg.MAX_ASTEROIDS:
                self._spawn_asteroid(ship)

        ship.update(dt)
        for asteroid in self.asteroids:
            asteroid.update(dt)
        for rocket in self.rockets:
            rocket.update(dt)
        self._update_explosions(dt)
        self._resolve_collisions(ship)
        self.rockets = [rocket for rocket in self.rockets if rocket.remaining]

    def _update_explosions(self, dt: float) -> None:
        """Продвинуть анимации и удалить завершённые взрывы."""
        for explosion in self.explosions:
            explosion.update(dt)
        self.explosions = [fx for fx in self.explosions if not fx.finished]

    def update(self, dt: float, turn: int, thrust: bool) -> None:
        """Обновить фон и продвинуть игровое состояние за dt секунд."""
        self.background.update(dt)
        ship = self.ship
        if dt <= 0:
            return
        if ship is None:
            self._update_explosions(dt)
            return

        ship.set_controls(turn, thrust)
        # Короткие шаги уменьшают риск пропустить столкновение.
        steps = ceil(dt / cfg.MAX_PHYSICS_STEP)
        for _ in range(steps):
            self._step(dt / steps, ship)
            if self.state is State.GAME_OVER:
                break

    def _draw_counter(self, x: int, label: str, value: int) -> None:
        """Рисует плашку счётчика с подписью и текущим значением."""
        rect = pygame.Rect((x, cfg.HUD_MARGIN), cfg.HUD_SIZE)
        pygame.draw.rect(
            self.screen, cfg.UI_DARK, rect, border_radius=cfg.UI_BUTTON_RADIUS
        )
        pygame.draw.rect(
            self.screen, cfg.UI_BORDER, rect, width=1,
            border_radius=cfg.UI_BUTTON_RADIUS,
        )
        caption = self.label_font.render(label, True, cfg.UI_MUTED)
        number = self.value_font.render(str(value), True, cfg.UI_TEXT)
        label_position = (x + cfg.HUD_INSET, rect.y + cfg.HUD_LABEL_Y)
        self.screen.blit(caption, label_position)
        self.screen.blit(number, (x + cfg.HUD_INSET, rect.y + cfg.HUD_VALUE_Y))

    def _draw_hud(self) -> None:
        """Показать счётчики очков и оставшихся возрождений."""
        self._draw_counter(cfg.HUD_MARGIN, "ОЧКИ", self.score)
        right_x = cfg.SCREEN_WIDTH - cfg.HUD_MARGIN - cfg.HUD_SIZE[0]
        self._draw_counter(right_x, "ЖИЗНИ", self.lives)

    def _card_center(self, y: int) -> tuple[int, int]:
        """Перевести координату элемента заставки в координаты окна."""
        return self.card.centerx, self.card.top + y

    def _draw_card(self) -> None:
        """Рисует центральную заставку и подсветку при наведении."""
        game_over = self.state is State.GAME_OVER
        self.screen.blit(self.card_panel, self.card)
        pygame.draw.rect(
            self.screen, cfg.UI_BORDER, self.card, width=1,
            border_radius=cfg.UI_CARD_RADIUS,
        )
        accent = pygame.Rect((0, 0), cfg.CARD_TOP_LINE)
        accent.midtop = self.card.midtop
        pygame.draw.rect(self.screen, cfg.UI_ACCENT, accent)

        status = "GAME OVER" if game_over else "КОСМИЧЕСКАЯ АРКАДА"
        label = self.label_font.render(status, True, cfg.UI_ACCENT)
        self.screen.blit(
            label, label.get_rect(center=self._card_center(cfg.CARD_STATUS_Y))
        )
        title_rect = self.title.get_rect(
            center=self._card_center(cfg.CARD_TITLE_Y)
        )
        self.screen.blit(self.title, title_rect)
        y = self.card.top + cfg.CARD_RULE_Y
        pygame.draw.line(
            self.screen, cfg.UI_BORDER,
            (self.card.left + cfg.CARD_RULE_INSET, y),
            (self.card.right - cfg.CARD_RULE_INSET, y),
        )

        button = pygame.Rect((0, 0), cfg.UI_BUTTON_SIZE)
        button.center = self._card_center(cfg.CARD_BUTTON_Y)
        hovered = self.card.collidepoint(pygame.mouse.get_pos())
        color = cfg.UI_HOVER if hovered else cfg.UI_ACCENT
        pygame.draw.rect(
            self.screen, color, button, border_radius=cfg.UI_BUTTON_RADIUS
        )
        action = "Играть снова" if game_over else "Начать игру"
        text = self.label_font.render(action, True, cfg.UI_DARK)
        self.screen.blit(text, text.get_rect(center=button.center))
        hint = self.label_font.render(
            "Щёлкните по заставке левой кнопкой мыши", True, cfg.UI_MUTED
        )
        self.screen.blit(
            hint, hint.get_rect(center=self._card_center(cfg.CARD_HINT_Y))
        )

    def draw(self) -> None:
        """Отрисовывает фон, объекты активной партии и интерфейс."""
        self.background.draw(self.screen)
        if self.ship is not None:
            for asteroid in self.asteroids:
                asteroid.draw(self.screen)
            for rocket in self.rockets:
                rocket.draw(self.screen)
            self.ship.draw(self.screen)
        else:
            self._draw_card()
        for explosion in self.explosions:
            explosion.draw(self.screen)
        self._draw_hud()
        pygame.display.flip()

    def run(self) -> None:
        """Запускает цикл обработки событий, симуляции и отрисовки."""
        while self.running:
            dt = min(self.clock.tick(cfg.FPS) / 1000, cfg.MAX_FRAME_TIME)
            for event in pygame.event.get():
                self.handle_event(event)
                if not self.running:
                    return
            keys = pygame.key.get_pressed()
            turn = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
            self.update(dt, turn, bool(keys[pygame.K_UP]))
            self.draw()


def main() -> None:
    """Открыть окно игры и освободить ресурсы Pygame при выходе."""
    pygame.display.init()
    pygame.font.init()
    try:
        Game().run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
