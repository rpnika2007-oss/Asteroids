"""Физика корабля, астероидов и ракет на тороидальном поле."""

from math import exp
from random import choice, uniform

import pygame
from pygame.math import Vector2

import settings as cfg
from effects import draw_wrapped


def torus_distance_squared(first: Vector2, second: Vector2) -> float:
    """Возвращает квадрат кратчайшего расстояния между точками тора."""
    half_width = cfg.SCREEN_WIDTH / 2
    half_height = cfg.SCREEN_HEIGHT / 2
    dx = (first.x - second.x + half_width) % cfg.SCREEN_WIDTH - half_width
    dy = (first.y - second.y + half_height) % cfg.SCREEN_HEIGHT - half_height
    return dx * dx + dy * dy


class GameObject:
    """Хранит кинематику, круговую коллизию и исходный спрайт объекта."""

    wraps: bool = True

    def __init__(
        self,
        position: Vector2,
        image: pygame.Surface,
        radius: float,
    ) -> None:
        """Копирует позицию и задаёт нулевые скорости."""
        self.position = position.copy()
        self.velocity = Vector2()
        self.angle = 0.0
        self.angular_speed = 0.0
        self.image = image
        self.radius = radius
        self.wrap()

    @property
    def forward(self) -> Vector2:
        """Возвращает единичный вектор вдоль носа вертикального спрайта."""
        return Vector2(0, -1).rotate(self.angle)

    def wrap(self) -> None:
        """Переносит центр через границы поля с сохранением остатка пути."""
        if self.wraps:
            self.position.x %= cfg.SCREEN_WIDTH
            self.position.y %= cfg.SCREEN_HEIGHT

    def update(self, dt: float) -> None:
        """Сдвигает и поворачивает объект за dt секунд."""
        self.position += self.velocity * dt
        self.angle = (self.angle + self.angular_speed * dt) % 360
        self.wrap()

    def touches(self, other: "GameObject") -> bool:
        """Проверяет пересечение кругов, включая области возле границ."""
        radius_sum = self.radius + other.radius
        distance = torus_distance_squared(self.position, other.position)
        return distance <= radius_sum ** 2

    def draw(self, target: pygame.Surface) -> None:
        """Вращает исходный спрайт относительно текущего центра."""
        # Vector2.rotate и transform.rotate используют разные знаки на экране.
        rotated = pygame.transform.rotate(self.image, -self.angle)
        if self.wraps:
            draw_wrapped(target, rotated, self.position)
        else:
            center = round(self.position.x), round(self.position.y)
            target.blit(rotated, rotated.get_rect(center=center))


class Ship(GameObject):
    """Корабль с управляемой угловой скоростью, тягой и инерцией."""

    def __init__(self, idle: pygame.Surface, thrust: pygame.Surface) -> None:
        """Создаёт корабль в центре и запоминает оба варианта спрайта."""
        super().__init__(Vector2(cfg.SCREEN_CENTER), idle, cfg.SHIP_RADIUS)
        self.idle_image = idle
        self.thrust_image = thrust
        self.engine_on = False
        self.shot_timer = 0.0
        self.protection = 0.0

    def set_controls(self, turn: int, thrust: bool) -> None:
        """Задаёт направление вращения и состояние двигателя."""
        self.angular_speed = turn * cfg.SHIP_TURN_SPEED
        self.engine_on = thrust
        self.image = self.thrust_image if thrust else self.idle_image

    def update(self, dt: float) -> None:
        """Обновляет угол, интегрирует тягу и ограничивает скорость."""
        # Средний угол шага точнее задаёт тягу при одновременном повороте.
        middle_angle = self.angle + self.angular_speed * dt / 2
        if self.engine_on:
            thrust = Vector2(0, -cfg.SHIP_ACCELERATION).rotate(middle_angle)
            self.velocity += thrust * dt
            self.velocity.clamp_magnitude_ip(cfg.SHIP_MAX_SPEED)
        else:
            self.velocity *= exp(-cfg.SHIP_DRAG * dt)
            if self.velocity.length_squared() < cfg.SHIP_STOP_SPEED ** 2:
                self.velocity.update(0, 0)
        self.shot_timer = max(0.0, self.shot_timer - dt)
        self.protection = max(0.0, self.protection - dt)
        super().update(dt)

    def fire(self, image: pygame.Surface) -> "Rocket | None":
        """Выпускает ракету из носа, когда завершилась задержка выстрела."""
        if self.shot_timer > cfg.TIME_EPSILON:
            return None
        self.shot_timer = cfg.SHOT_INTERVAL
        muzzle = self.position + self.forward * cfg.SHIP_NOSE
        rocket = Rocket(muzzle, self.angle, image)
        return rocket if rocket.in_bounds else None

    def respawn(self) -> None:
        """Сбрасывает кинематику и включает защиту в центре поля."""
        self.position.update(cfg.SCREEN_CENTER)
        self.velocity.update(0, 0)
        self.angle = 0.0
        self.set_controls(0, False)
        self.shot_timer = 0.0
        self.protection = cfg.RESPAWN_PROTECTION

    def draw(self, target: pygame.Surface) -> None:
        """Показывает корабль с миганием во время временной защиты."""
        if int(self.protection / cfg.BLINK_INTERVAL) % 2 == 0:
            super().draw(target)


class Asteroid(GameObject):
    """Камень со случайным направлением, скоростью и вращением."""

    def __init__(
        self, position: Vector2, image: pygame.Surface, radius: float
    ) -> None:
        """Выбирает начальный угол и случайные скорости камня."""
        super().__init__(position, image, radius)
        direction = Vector2(0, -1).rotate(uniform(0, 360))
        self.velocity = direction * uniform(*cfg.ASTEROID_SPEED)
        self.angle = uniform(0, 360)
        self.angular_speed = choice((-1, 1)) * uniform(*cfg.ASTEROID_SPIN)


class Rocket(GameObject):
    """Снаряд с неизменной ориентацией, скоростью и временем жизни."""

    wraps = False

    def __init__(
        self, muzzle: Vector2, angle: float, image: pygame.Surface
    ) -> None:
        """Ставит хвост спрайта на нос корабля и задаёт вектор полёта."""
        offset = Vector2(0, -cfg.ROCKET_TAIL).rotate(angle)
        super().__init__(muzzle + offset, image, cfg.ROCKET_RADIUS)
        self.angle = angle
        self.velocity = self.forward * cfg.ROCKET_SPEED
        self.remaining = cfg.ROCKET_LIFETIME

    @property
    def in_bounds(self) -> bool:
        """Проверяет, находится ли центр ракеты внутри игрового поля."""
        return (
            0 <= self.position.x < cfg.SCREEN_WIDTH
            and 0 <= self.position.y < cfg.SCREEN_HEIGHT
        )

    def update(self, dt: float) -> None:
        """Продвигает ракету в пределах оставшегося времени жизни."""
        super().update(min(dt, self.remaining))
        remaining = self.remaining - dt
        self.remaining = remaining if remaining > cfg.TIME_EPSILON else 0.0
