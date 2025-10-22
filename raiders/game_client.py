# game_client.py
import socket
import pickle
import struct
import pygame
import sys
import time
import math

import raiders
MSG_LEN_STRUCT = struct.Struct("!I")


def send_msg(sock, obj):
    data = pickle.dumps(obj)
    sock.sendall(MSG_LEN_STRUCT.pack(len(data)) + data)


def recv_msg(sock):
    try:
        header = sock.recv(MSG_LEN_STRUCT.size)
        if not header:
            return None
        (length,) = MSG_LEN_STRUCT.unpack(header)
        data = b""
        while len(data) < length:
            packet = sock.recv(length - len(data))
            if not packet:
                return None
            data += packet
        return pickle.loads(data)
    except Exception:
        return None


class GameClient:
    def __init__(self, server_ip, port, player_id):
        pygame.init()
        self.server_ip = server_ip
        self.port = port
        self.player_id = player_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((server_ip, port))
        self.sock.settimeout(None)  # blocking for main loop
        # register with server
        send_msg(self.sock, {'type': 'register', 'player_id': self.player_id})

        # setup pygame window (will resize to incoming frames)
        self.screen = pygame.display.set_mode((800, 800))
        pygame.display.set_caption(f"Player {self.player_id} - Client")
        self.clock = pygame.time.Clock()
        self.running = True

        self.food_img = pygame.image.load("assets/food.png")
        self.wood_img = pygame.image.load("assets/wood.png")
        self.stone_img = pygame.image.load("assets/stone.png")
        self.font = pygame.font.Font(None, 30) 
        self.font2 = pygame.font.Font(None, 25) 
        self.last_action = (1,1,0,0,0)

    def build_action_from_input(self, player_angle, relative_pos):
        """
        Build action tuple (ax, ay, active, action, angle) matching PlayerAgent.step().
        """

        keys = pygame.key.get_pressed()

        # --- Active ability / weapon selection ---
        active = 0
        if keys[pygame.K_1]: active = 1
        if keys[pygame.K_2]: active = 2
        if keys[pygame.K_3]: active = 3
        if keys[pygame.K_4]: active = 4
        if keys[pygame.K_5]: active = 5
        if keys[pygame.K_6]: active = 6
        if keys[pygame.K_q]: active = 7
        if keys[pygame.K_r]: active = 8
        if keys[pygame.K_e]: active = 9

        # --- Movement (starts at 1,1 and adjusts with WASD) ---
        ax, ay = 1, 1
        if keys[pygame.K_a]: ax -= 1
        if keys[pygame.K_d]: ax += 1
        if keys[pygame.K_s]: ay -= 1
        if keys[pygame.K_w]: ay += 1

        # --- Action (attack or similar) ---
        action = pygame.mouse.get_pressed()[0]

        # --- Angle computation based on mouse vs. screen center ---
        mx, my = pygame.mouse.get_pos()
        window_w, window_h = self.screen.get_size()
        cx, cy = relative_pos[0] * window_w / 600, relative_pos[1] * window_h / 600
        dx, dy = mx - cx, my - cy
        target_angle = -math.atan2(dy, dx)

        self.last_action = (ax, ay, active, action, target_angle)

        return self.last_action


    def run(self):
        try:
            while self.running:
                msg = recv_msg(self.sock)
                if msg is None:
                    print("[client] connection closed by server")
                    break

                
                # handle server messages
                mtype = msg.get('type')
                if mtype == 'frame':
                    #img_bytes = msg['img_bytes']
                    size = msg['size']
                    info = msg.get('info')
                    player_pos = info["positions"][self.player_id]
                    player_angle = info["angles"][self.player_id]
                    objects = info['objects']
                    
                    w, h = size
                    px, py = info["positions"][self.player_id]
                    crop_w, crop_h = 600, 600

                    x0 = int(px - crop_w / 2)
                    y0 = int(py - crop_h / 2)

                    # clamp so we don't go out of bounds
                    x0 = max(0, min(x0, w - crop_w))
                    y0 = max(0, min(y0, h - crop_h))

                    relative_pos = (px - x0, 600 + y0 - py)
                    # reconstruct surface from raw RGB bytes
                    try:
                        frame_surf = pygame.Surface((600, 600), pygame.SRCALPHA)
                        frame_surf.fill((100, 170, 70))
                        players = []
                        for obj in objects:
                            dx, dy = obj[1]-player_pos[0], obj[2]-player_pos[1]
                            if math.dist((obj[1],obj[2]), (x0+300,y0+300)) > 550: 
                                continue
                            screen_pos = dx+relative_pos[0], dy+600-relative_pos[1]
                            raiders.StaticDisplays.display(frame_surf, screen_pos, obj)

                            if obj[0] == -1:
                                players.append(obj)
                        
                        for obj in players:
                            if obj[3] <= 0:
                                continue
                            dx, dy = obj[1]-player_pos[0], obj[2]-player_pos[1]
                            screen_pos = dx+relative_pos[0], dy+600-relative_pos[1]
                            bar_width = 40
                            health_ratio = obj[3] / 20
                            pygame.draw.rect(frame_surf, (40,40,40), (screen_pos[0]-bar_width/2, screen_pos[1]+20, bar_width, 6))
                            pygame.draw.rect(frame_surf, (140,210,100), (screen_pos[0]-(bar_width-3)/2, screen_pos[1]+21, (bar_width-3)*min(1, health_ratio), 3))
                            if health_ratio > 1:
                                absorption_ratio = health_ratio - 1
                                pygame.draw.rect(frame_surf, (255,220,90), (screen_pos[0]+(bar_width-3)*(0.5-absorption_ratio), screen_pos[1]+21, (bar_width-3)*absorption_ratio, 3))  


                    except Exception as e:
                        print(f"[client] failed to construct image: {e}")
                        continue

                    w, h = size
                    px, py = info["positions"][self.player_id]
                    crop_w, crop_h = 600, 600

                    x0 = int(px - crop_w / 2)
                    y0 = int(py - crop_h / 2)

                    # clamp so we don't go out of bounds
                    x0 = max(0, min(x0, w - crop_w))
                    y0 = max(0, min(y0, h - crop_h))

                    relative_pos = (px - x0, 600 + y0 - py)

                    # fit frame to window
                    window_size = self.screen.get_size()
                    if window_size != size:
                        # scale to window size (fit)
                        frame_surf = pygame.transform.scale(frame_surf, window_size)

                    # blit and flip
                    frame_surf = pygame.transform.flip(frame_surf, False, True)

                    for img, text, y in zip(
                        (self.food_img, self.wood_img, self.stone_img), 
                        (info["food"][self.player_id], info["wood"][self.player_id], info["stone"][self.player_id]), 
                        (420, 470, 520)):
                        frame_surf.blit(img, (15, self.screen.get_size()[1] - 600 + y))
                        text_surf = self.font.render(str(int(text)), True, (255,255,255))
                        frame_surf.blit(text_surf, (60, self.screen.get_size()[1] - 600 + y+10))

                    self.screen.blit(frame_surf, (0, 0))
                    pygame.display.flip()

                    # capture pygame events & allow quitting
                    for ev in pygame.event.get():
                        if ev.type == pygame.QUIT:
                            self.running = False

                    # build action from local input and send to server
                    action = self.build_action_from_input(player_angle, relative_pos)
                    send_msg(self.sock, {'type': 'action', 'player_id': self.player_id, 'action': action})

                    # lightweight tick limit to avoid burning 100% CPU
                    self.clock.tick(60)

                elif mtype == 'server_shutdown':
                    print("[client] server is shutting down")
                    break
                else:
                    # ignore unknown messages
                    pass

        except KeyboardInterrupt:
            print("[client] KeyboardInterrupt, exiting")
        finally:
            try:
                self.sock.close()
            except:
                pass
            pygame.quit()
            print("[client] stopped")


if __name__ == "__main__":
    # Example usage:
    # python game_client.py <server_ip> <port> <player_id>
    if len(sys.argv) >= 4:
        print("connecting to server")
        server_ip = sys.argv[1]
        port = int(sys.argv[2])
        player_id = int(sys.argv[3])
    else:
        server_ip = "0.0.0.0"
        port = 9999
        player_id = 0

    client = GameClient(server_ip, port, player_id)
    client.run()
