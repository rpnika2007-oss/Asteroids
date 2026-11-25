"""Загрузка графики, бесшовный фон и тайловая анимация взрыва."""

import pygame
from pygame.math import Vector2

import settings as cfg


def load_image(name: str) -> pygame.Surface:
    """Загрузить изображение с прозрачностью в формате экрана."""
    return pygame.image.load(str(cfg.ASSETS_DIR / name)).convert_alpha()


def draw_wrapped(
    target: pygame.Surface, image: pygame.Surface, center: Vector2
) -> None:
    """Рисует спрайт и его продолжения на противоположных краях."""
    rect = image.get_rect(center=(round(center.x), round(center.y)))
    width, height = target.get_size()
    x_offsets = [0]
    y_offsets = [0]
    if rect.left < 0:
        x_offsets.append(width)
    if rect.right > width:
        x_offsets.append(-width)
    if rect.top < 0:
        y_offsets.append(height)
    if rect.bottom > height:
        y_offsets.append(-height)
    for dx in x_offsets:
        for dy in y_offsets:
            target.blit(image, rect.move(dx, dy))


class Background:
    """Рисует неподвижные звёзды и прокручивает слой камней."""

    def __init__(self) -> None:
        """Загружает и масштабирует оба слоя под размеры экрана."""
        self.stars = self._load_layer("space.png")
        self.drift = self._load_layer("drift.png")
        self.drift.set_alpha(cfg.BACKGROUND_ALPHA)
        self.offset = 0.0

    @staticmethod
    def _load_layer(name: str) -> pygame.Surface:
        """Приводит размер изображения к размеру игрового поля."""
        layer = load_image(name)
        if layer.get_size() != cfg.SCREEN_SIZE:
            layer = pygame.transform.smoothscale(layer, cfg.SCREEN_SIZE)
        return layer

    def update(self, dt: float) -> None:
        """Накапливает смещение за dt секунд с циклом в одну ширину."""
        self.offset = (self.offset + cfg.BACKGROUND_SPEED * dt) % (
            cfg.SCREEN_WIDTH
        )

    def draw(self, target: pygame.Surface) -> None:
        """Стыкует две копии слоя без пропусков при любом смещении."""
        x = -int(self.offset)
        target.blit(self.stars, (0, 0))
        target.blit(self.drift, (x, 0))
        target.blit(self.drift, (x + cfg.SCREEN_WIDTH, 0))


class Explosion:
    """Однократная анимация взрыва в точке столкновения."""

    def __init__(
        self, position: Vector2, frames: tuple[pygame.Surface, ...]
    ) -> None:
        """Скопировать позицию и запустить отдельный таймер анимации."""
        self.position = position.copy()
        self.frames = frames
        self.elapsed = 0.0

    @staticmethod
    def load_frames() -> tuple[pygame.Surface, ...]:
        """Вернуть кадры спрайт-листа слева направо и сверху вниз.

        Размер изображения должен точно соответствовать сетке тайлов.
        """
        sheet = load_image("explosion.png")
        width, height = cfg.EXPLOSION_TILE
        expected = (width * cfg.EXPLOSION_COLUMNS, height * cfg.EXPLOSION_ROWS)
        if sheet.get_size() != expected:
            raise ValueError(f"Размер спрайт-листа должен быть {expected}")
        return tuple(
            sheet.subsurface((col * width, row * height, width, height)).copy()
            for row in range(cfg.EXPLOSION_ROWS)
            for col in range(cfg.EXPLOSION_COLUMNS)
        )

    @property
    def frame_index(self) -> int:
        """Вычисляет текущий номер кадра по времени с начала взрыва."""
        # Индекс равен числу полностью прошедших интервалов показа.
        return int((self.elapsed + cfg.TIME_EPSILON) / cfg.EXPLOSION_INTERVAL)

    @property
    def finished(self) -> bool:
        """Проверяет, закончился ли показ последнего кадра."""
        return self.frame_index >= len(self.frames)

    def update(self, dt: float) -> None:
        """Продвигает таймер анимации на dt секунд."""
        self.elapsed += dt

    def draw(self, target: pygame.Surface) -> None:
        """Рисует только текущий кадр действующего взрыва."""
        if not self.finished:
            draw_wrapped(target, self.frames[self.frame_index], self.position)
