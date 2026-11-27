import os
import sys
import math
import random
import pygame

# ---------- Инициализация ----------
pygame.init()
W, H = 960, 540
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Boss Fight - Cuphead Style")
clock = pygame.time.Clock()

# Пути к PNG-спрайтам (положите файлы рядом со скриптом или укажите свой путь)
PLAYER_SPRITE_PATH = "player_1.png"
BOSS_SPRITE_PATH = "boss_1.png"
TILESET_PATH = "tilesetgrass.png"
BULLET_SHEET_PATH = "FoxShotSheet.png"

def get_font(size, bold=False):
    return pygame.font.SysFont("dejavusansmono,consolas,couriernew,arial", size, bold=bold)


def load_sprite(path, size, fallback_color):
    """Загружает PNG с альфа-каналом и подгоняет размер; при ошибке возвращает заглушку."""
    w, h = size
    if path and os.path.isfile(path):
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.scale(img, (w, h))
        except pygame.error:
            pass

    fallback = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(fallback, (*fallback_color, 170), (0, 0, w, h), border_radius=8)
    pygame.draw.rect(fallback, (0, 0, 0, 220), (0, 0, w, h), 3, border_radius=8)
    return fallback


def load_ground_tile(path, target_h):
    """Вырезает горизонтальную полосу земли с травой из тайлсета и масштабирует без размытия."""
    if path and os.path.isfile(path):
        try:
            sheet = pygame.image.load(path).convert_alpha()
            sw, sh = sheet.get_size()
            strip_w = max(16, int(sw * 0.25))
            strip_h = max(16, int(sh * 0.22))
            strip_x = 6
            strip_y = max(0, sh - strip_h)

            tile = sheet.subsurface((strip_x, strip_y, strip_w, strip_h)).copy()

            # Целый множитель по высоте, чтобы пиксели не "плыли" по пропорциям
            scale_factor = max(1, round(target_h / max(1, tile.get_height())))
            scaled_w = tile.get_width() * scale_factor
            scaled_h = tile.get_height() * scale_factor
            return pygame.transform.scale(tile, (scaled_w, scaled_h))
        except pygame.error:
            pass

    fallback = pygame.Surface((64, target_h), pygame.SRCALPHA)
    fallback.fill((90, 58, 32))
    pygame.draw.rect(fallback, (46, 204, 113), (0, 0, 64, max(8, target_h // 4)))
    return fallback


def load_player_bullet_sprites(path, scale=2):
    """Загружает синий огонёк из спрайт-листа."""
    if path and os.path.isfile(path):
        try:
            sheet = pygame.image.load(path).convert_alpha()
            # Координаты синего маленького ромба (6-й столбец в 4-м ряду сверху;
            # если нужно точнее подправить рамку — подстрой rect (x, y, w, h))
            rect = pygame.Rect(36, 51, 5, 12)
            raw = sheet.subsurface(rect).copy()

            # В листе огонёк смотрит вверх, поэтому поворачиваем по направлению полёта
            right_img = pygame.transform.rotate(raw, -90)
            right_img = pygame.transform.scale_by(right_img, scale)
            left_img = pygame.transform.flip(right_img, True, False)
            return right_img, left_img
        except (pygame.error, ValueError):
            pass

    return None, None

font_big = get_font(72, True)
font_med = get_font(28)
font_small = get_font(18, True)

# ---------- Константы ----------
GRAVITY = 0.9
JUMP = -18
SPEED = 6
GROUND_Y = H - 45

# Отдельный слой для экранной тряски
game_surf = pygame.Surface((W, H))


# ============================================================
# СНАРЯДЫ И ЧАСТИЦЫ
# ============================================================
class Bullet:
    def __init__(self, x, y, vx, vy, r, gravity=0, life=180):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.r = r
        self.gravity = gravity
        self.life = life


class Particle:
    def __init__(self, x, y, vx, vy, color, life):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.life = life
        self.max_life = life


# ============================================================
# ИГРОК
# ============================================================
class Player:
    def __init__(self, sprite_path=PLAYER_SPRITE_PATH):
        self.w, self.h = 56, 68
        self.sprite_left = load_sprite(sprite_path, (self.w, self.h), (70, 170, 255))
        self.sprite_right = pygame.transform.flip(self.sprite_left, True, False)
        self.reset()

    def reset(self):
        self.x = 200.0
        self.y = float(GROUND_Y - self.h)
        self.vx = self.vy = 0.0
        self.on_ground = True
        self.hp, self.max_hp = 3, 3
        self.facing = 1
        self.shoot_cd = 0
        self.dash_cd = 0
        self.dash_time = 0
        self.invuln = 0
        self.alive = True
        self.anim_t = 0

    def update(self, keys, game):
        if not self.alive:
            return
        self.anim_t += 1
        self.shoot_cd = max(0, self.shoot_cd - 1)
        self.dash_cd = max(0, self.dash_cd - 1)
        self.invuln = max(0, self.invuln - 1)

        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        jump = keys[pygame.K_SPACE] or keys[pygame.K_w] or keys[pygame.K_UP]
        fire = keys[pygame.K_x] or keys[pygame.K_j]
        dash = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or keys[pygame.K_k]

        # Рывок
        if self.dash_time > 0:
            self.dash_time -= 1
            self.vx = self.facing * 14
            self.vy = 0
        else:
            if left:
                self.vx = -SPEED
                self.facing = -1
            elif right:
                self.vx = SPEED
                self.facing = 1
            else:
                self.vx *= 0.7

        # Прыжок
        if jump and self.on_ground:
            self.vy = JUMP
            self.on_ground = False

        # Старт рывка (с i-frames)
        if dash and self.dash_cd == 0 and self.dash_time == 0:
            self.dash_time = 12
            self.dash_cd = 45
            self.invuln = max(self.invuln, 14)
            for _ in range(6):
                game.particles.append(Particle(
                    self.x + self.w / 2, self.y + self.h / 2,
                    random.uniform(-4, 4), random.uniform(-4, 0),
                    (160, 224, 255), 30))

        # Стрельба
        if fire:
            self.shoot(game)

        # Гравитация
        if self.dash_time == 0:
            self.vy += GRAVITY
            self.vy = min(self.vy, 22)

        self.x += self.vx
        self.y += self.vy

        # Границы
        self.x = max(0, min(W - self.w, self.x))
        if self.y + self.h >= GROUND_Y:
            self.y = GROUND_Y - self.h
            self.vy = 0
            self.on_ground = True
        else:
            self.on_ground = False

        # Контакт с боссом
        b = game.boss
        if self.invuln == 0 and \
           self.x < b.x + b.w and self.x + self.w > b.x and \
           self.y < b.y + b.h and self.y + self.h > b.y:
            self.hit(game)

    def shoot(self, game):
        if self.shoot_cd > 0:
            return
        self.shoot_cd = 8
        game.bullets.append(Bullet(
            self.x + self.w / 2 + self.facing * 25,
            self.y + self.h / 2 - 5,
            self.facing * 14, 0, 7))

    def hit(self, game):
        self.hp -= 1
        self.invuln = 60
        game.screen_shake = 12
        for _ in range(12):
            game.particles.append(Particle(
                self.x + self.w / 2, self.y + self.h / 2,
                random.uniform(-4, 4), random.uniform(-6, 2),
                (255, 64, 64), 30))
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            if game.state == 'playing':
                game.state = 'lose'

    def draw(self, surf):
        if not self.alive:
            return
        if self.invuln > 0 and (self.invuln // 4) % 2 == 0:
            return  # мерцание при неуязвимости

        img = self.sprite_right if self.facing > 0 else self.sprite_left
        surf.blit(img, (int(self.x), int(self.y)))


# ============================================================
# БОСС
# ============================================================
class Boss:
    def __init__(self, sprite_path=BOSS_SPRITE_PATH):
        self.w, self.h = 170, 200
        self.x = 700.0
        self.y = float(GROUND_Y - self.h)
        self.max_hp = 100
        self.sprite = load_sprite(sprite_path, (self.w, self.h), (220, 60, 60))
        self.reset()
        self.mask = pygame.mask.from_surface(self.sprite)

    def reset(self):
        self.hp = self.max_hp
        self.phase = 1
        self.attack = 'idle'
        self.attack_step = 0
        self.attack_timer = 120
        self.anim_t = 0
        self.hurt = 0
        self.dying = 0

    def update(self, game):
        if self.hp <= 0:
            if self.dying == 0:
                self.dying = 90
                cx, cy = self.x + self.w / 2, self.y + self.h / 2
                for _ in range(40):
                    game.particles.append(Particle(
                        cx, cy,
                        random.uniform(-6, 6), random.uniform(-8, 4),
                        (255, 80, 80), 45))
            self.dying -= 1
            if self.dying <= 0 and game.state == 'playing':
                game.state = 'win'
            return

        self.anim_t += 1
        self.hurt = max(0, self.hurt - 1)

        # Смена фаз
        if self.hp < self.max_hp * 0.5 and self.phase == 1:
            self.phase = 2
            game.screen_shake = 20
            for _ in range(25):
                game.particles.append(Particle(
                    self.x + self.w / 2, self.y + self.h / 2,
                    random.uniform(-6, 6), random.uniform(-8, 4),
                    (255, 215, 0), 40))
        if self.hp < self.max_hp * 0.25 and self.phase == 2:
            self.phase = 3
            game.screen_shake = 20
            for _ in range(25):
                game.particles.append(Particle(
                    self.x + self.w / 2, self.y + self.h / 2,
                    random.uniform(-6, 6), random.uniform(-8, 4),
                    (255, 48, 48), 40))

        # Выбор атаки
        self.attack_timer -= 1
        if self.attack_timer <= 0:
            self.attack = random.choice(['slam', 'spread', 'rain'])
            self.attack_step = 0
            self.attack_timer = {1: 140, 2: 100, 3: 75}[self.phase]

        p = game.player

        # ---- SLAM: прыжок + волны ----
        if self.attack == 'slam':
            self.attack_step += 1
            if self.attack_step == 50:
                bx = p.x + p.w / 2
                for _ in range(3):
                    game.boss_bullets.append(Bullet(
                        bx + random.uniform(-40, 40), GROUND_Y - 10,
                        random.uniform(-3, 3), random.uniform(-12, -8),
                        15, gravity=0.4, life=120))

        # ---- SPREAD: веер ----
        elif self.attack == 'spread':
            if self.attack_step > 10 and self.attack_step % 15 == 0 and self.attack_step < 90:
                cx, cy = self.x + self.w / 2, self.y + self.h / 2
                ang = math.atan2(p.y + p.h / 2 - cy, p.x + p.w / 2 - cx)
                count = 3 if self.phase >= 1 else 2
                spread = 1.2
                for i in range(count):
                    a = ang + (i - (count - 1) / 2) * (spread / max(1, count - 1))
                    game.boss_bullets.append(Bullet(
                        cx, cy, math.cos(a) * 7, math.sin(a) * 7,
                        12, gravity=0, life=180))
            self.attack_step += 1

        # ---- RAIN: дождь сверху ----
        elif self.attack == 'rain':
            if self.attack_step > 10 and self.attack_step % 8 == 0 and self.attack_step < 100:
                game.boss_bullets.append(Bullet(
                    random.uniform(100, W - 100), -20,
                    0, 6, 10, gravity=0.15, life=200))
            self.attack_step += 1

    def draw(self, surf):
        if self.hp <= 0 and self.dying <= 0:
            return

        dx = self.x
        dy = self.y + math.sin(self.anim_t * 0.05) * 6

        if self.hurt > 0:
            dx += random.uniform(-3, 3)
            dy += random.uniform(-3, 3)

        img = self.sprite.copy()
        if self.phase == 2:
            img.fill((255, 190, 170, 255), special_flags=pygame.BLEND_RGBA_MULT)
        elif self.phase == 3:
            img.fill((255, 110, 110, 255), special_flags=pygame.BLEND_RGBA_MULT)

        surf.blit(img, (int(dx), int(dy)))

        if self.hurt > 0:
            # Цвет вспышки: можно заменить на (255, 255, 255, 180) для белой вспышки
            # или (255, 90, 90, 170) для мягкого красного импульса
            flash = self.mask.to_surface(
                setcolor=(255, 90, 90, 170),
                unsetcolor=(0, 0, 0, 0)
            ).convert_alpha()
            surf.blit(flash, (int(dx), int(dy)))

        # Предупреждение о SLAM
        if self.attack == 'slam' and 20 < self.attack_step < 50:
            cx = self.x + self.w / 2
            cy = self.y + self.h / 2
            r = 30 + math.sin(self.attack_step * 0.5) * 10
            s = pygame.Surface((int(r * 2), int(r * 2)), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 0, 0, 128), (int(r), int(r)), int(r))
            surf.blit(s, (int(cx - r), int(cy - 180 - r)))


# ============================================================
# ИГРА
# ============================================================
class Game:
    def __init__(self):
        self.player = Player()
        self.boss = Boss()
        self.bullets = []
        self.boss_bullets = []
        self.particles = []
        self.state = 'playing'
        self.screen_shake = 0
        self.running = True
        self.ground_tile = load_ground_tile(TILESET_PATH, H - GROUND_Y)
        self.bullet_right, self.bullet_left = load_player_bullet_sprites(BULLET_SHEET_PATH, scale=2)

    def reset(self):
        self.player.reset()
        self.boss.reset()
        self.bullets.clear()
        self.boss_bullets.clear()
        self.particles.clear()
        self.state = 'playing'
        self.screen_shake = 0

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                if event.key == pygame.K_r and self.state != 'playing':
                    self.reset()

    def update(self):
        if self.state == 'playing':
            keys = pygame.key.get_pressed()
            self.player.update(keys, self)
            self.boss.update(self)
            self.update_bullets()
        self.update_particles()
        self.screen_shake = max(0, self.screen_shake * 0.85)
        if self.screen_shake < 0.5:
            self.screen_shake = 0

    def update_bullets(self):
        alive = []
        for b in self.bullets:
            b.x += b.vx
            b.y += b.vy
            if b.x < -20 or b.x > W + 20:
                continue
            bs = self.boss
            if bs.hp > 0 and \
               b.x + b.r > bs.x and b.x - b.r < bs.x + bs.w and \
               b.y + b.r > bs.y and b.y - b.r < bs.y + bs.h:
                bs.hp = max(0, bs.hp - 1)
                bs.hurt = 6
                for _ in range(6):
                    self.particles.append(Particle(
                        b.x, b.y,
                        random.uniform(-3, 3), random.uniform(-4, 2),
                        (0, 240, 170), 20))
                continue
            alive.append(b)
        self.bullets = alive

        alive_b = []
        p = self.player
        for b in self.boss_bullets:
            b.x += b.vx
            b.vy += b.gravity
            b.y += b.vy
            b.life -= 1
            if b.life <= 0 or b.y > H + 50 or b.x < -50 or b.x > W + 50:
                continue
            if p.alive and p.invuln == 0:
                dx = b.x - (p.x + p.w / 2)
                dy = b.y - (p.y + p.h / 2)
                if math.hypot(dx, dy) < b.r + 20:
                    p.hit(self)
                    continue
            alive_b.append(b)
        self.boss_bullets = alive_b

    def update_particles(self):
        alive = []
        for pt in self.particles:
            pt.x += pt.vx
            pt.y += pt.vy
            pt.vy += 0.3
            pt.life -= 1
            if pt.life > 0:
                alive.append(pt)
        self.particles = alive

    # ---------- Отрисовка ----------
    def draw(self):
        sx = random.uniform(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0
        sy = random.uniform(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0

        self.draw_background(game_surf)
        self.boss.draw(game_surf)
        self.draw_bullets(game_surf)
        self.player.draw(game_surf)
        self.draw_particles(game_surf)

        screen.fill((0, 0, 0))
        screen.blit(game_surf, (sx, sy))

        self.draw_ui(screen)
        if self.state != 'playing':
            self.draw_end_screen(screen)

    def draw_background(self, surf):
        if self.boss.phase == 1:
            top, bot = (135, 206, 235), (244, 208, 63)
        elif self.boss.phase == 2:
            top, bot = (230, 126, 34), (192, 57, 43)
        else:
            top, bot = (44, 24, 16), (139, 0, 0)

        for y in range(H):
            t = y / H
            col = (int(top[0] + (bot[0] - top[0]) * t),
                   int(top[1] + (bot[1] - top[1]) * t),
                   int(top[2] + (bot[2] - top[2]) * t))
            pygame.draw.line(surf, col, (0, y), (W, y))

        # Облака
        cloud_col = (255, 255, 255, 180) if self.boss.phase == 1 else (60, 30, 30, 180)
        for i in range(5):
            cx = ((i * 240 + self.boss.anim_t * 0.3) % (W + 200)) - 100
            cy = 80 + i * 25
            s = pygame.Surface((180, 60), pygame.SRCALPHA)
            pygame.draw.ellipse(s, cloud_col, (0, 10, 100, 50))
            pygame.draw.ellipse(s, cloud_col, (40, 5, 80, 50))
            pygame.draw.ellipse(s, cloud_col, (80, 10, 100, 50))
            surf.blit(s, (int(cx - 90), int(cy - 30)))

        # Земля
        tile_w = self.ground_tile.get_width()
        for x in range(0, W, tile_w):
            piece = self.ground_tile.copy()
            if self.boss.phase == 2:
                piece.fill((255, 160, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
            elif self.boss.phase == 3:
                piece.fill((140, 60, 60, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(piece, (x, GROUND_Y))

        pygame.draw.line(surf, (0, 0, 0), (0, GROUND_Y), (W, GROUND_Y), 3)

    def draw_bullets(self, surf):
        for b in self.bullets:
            if self.bullet_right and self.bullet_left:
                img = self.bullet_right if b.vx >= 0 else self.bullet_left
                surf.blit(img, img.get_rect(center=(int(b.x), int(b.y))))
            else:
                pygame.draw.circle(surf, (0, 0, 0), (int(b.x), int(b.y)), b.r)

        for b in self.boss_bullets:
            pygame.draw.circle(surf, (0, 255, 0), (int(b.x), int(b.y)), b.r)
            pygame.draw.circle(surf, (0, 0, 0), (int(b.x), int(b.y)), b.r, 3)
            pygame.draw.circle(surf, (232, 180, 255),
                               (int(b.x - b.r // 4), int(b.y - b.r // 4)), b.r // 2)

    def draw_particles(self, surf):
        for p in self.particles:
            alpha = max(0, min(255, int(p.life / p.max_life * 255)))
            s = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.rect(s, (*p.color, alpha), (0, 0, 6, 6))
            surf.blit(s, (int(p.x - 3), int(p.y - 3)))

    def draw_ui(self, surf):
        for i in range(self.player.max_hp):
            self.draw_heart(surf, 30 + i * 45, 30, i < self.player.hp)

        bw, bh = 500, 26
        bx = W // 2 - bw // 2
        by = 30
        pygame.draw.rect(surf, (0, 0, 0), (bx - 3, by - 3, bw + 6, bh + 6))
        pygame.draw.rect(surf, (58, 26, 26), (bx, by, bw, bh))

        frac = max(0, self.boss.hp / self.boss.max_hp)
        if self.boss.phase == 1:
            c = (231, 76, 60)
        elif self.boss.phase == 2:
            c = (192, 57, 43)
        else:
            c = (139, 0, 0)
        pygame.draw.rect(surf, c, (bx, by, int(bw * frac), bh))
        pygame.draw.rect(surf, (255, 255, 255, 80), (bx, by, int(bw * frac), bh // 3))
        pygame.draw.rect(surf, (255, 255, 255), (bx, by, bw, bh), 2)

        label = font_small.render("THE VISCOUS", True, (255, 255, 255))
        surf.blit(label, (W // 2 - label.get_width() // 2, by - 22))

    def draw_heart(self, surf, x, y, filled):
        color = (255, 48, 80, 255) if filled else (55, 55, 62, 255)
        outline_col = (0, 0, 0, 255)

        # Размер холста под одно сердце с запасом под обводку
        sw, sh = 40, 36
        cx, cy = sw // 2, 13
        r = 8

        def stamp_heart(target, col):
            pygame.draw.circle(target, col, (cx - 6, cy), r)
            pygame.draw.circle(target, col, (cx + 6, cy), r)
            pygame.draw.polygon(target, col, [
                (cx - 14, cy + 2),
                (cx + 14, cy + 2),
                (cx, cy + 18),
            ])

        # 1. Внешняя обводка за счёт сдвига силуэта на 2 px во все стороны
        outline_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)]:
            temp = pygame.Surface((sw, sh), pygame.SRCALPHA)
            stamp_heart(temp, outline_col)
            outline_surf.blit(temp, (dx, dy))

        # 2. Внутренняя заливка сердца
        fill_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        stamp_heart(fill_surf, color)

        # 3. Небольшой блик на заполненном сердце
        if filled:
            pygame.draw.circle(fill_surf, (255, 175, 190, 190), (cx - 7, cy - 2), 3)

        # Собираем на одном слое, чтобы у сердца был единый альфа-канал
        heart_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
        heart_surf.blit(outline_surf, (0, 0))
        heart_surf.blit(fill_surf, (0, 0))

        surf.blit(heart_surf, (int(x - sw // 2), int(y - 14)))

    def draw_end_screen(self, surf):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surf.blit(overlay, (0, 0))

        if self.state == 'win':
            t = font_big.render("ПОБЕДА!", True, (255, 215, 0))
            s = font_med.render("Босс повержен!", True, (255, 255, 255))
        else:
            t = font_big.render("GAME OVER", True, (255, 48, 48))
            s = font_med.render("Ты пал в бою...", True, (255, 255, 255))

        surf.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 60))
        surf.blit(s, (W // 2 - s.get_width() // 2, H // 2 + 30))

        hint = font_small.render("Нажми R чтобы начать заново", True, (170, 170, 170))
        surf.blit(hint, (W // 2 - hint.get_width() // 2, H // 2 + 100))


# ============================================================
# ЗАПУСК
# ============================================================
def main():
    game = Game()
    while game.running:
        game.handle_events()
        game.update()
        game.draw()
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()