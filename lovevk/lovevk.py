import requests
import json
import time
import hashlib
import threading
import base64
import urllib
import html
from websocket import create_connection
from .utils import objects
from .user import User
from .room import Room
from .viral import Viral
from .socket import Callbacks, SocketHandler, Events

class Client(Callbacks, SocketHandler):
    def __init__(self, auth_key: str, user_id: str, session_key: str = None,
        client_type: int = 1, websocket: bool = False, mobi: bool = True, avatar: str = "",
        room_iders: int = 1, first_name: str = "Игрок") -> None:
        """ В библиотеке возможна авторизация как через ВК, так и через ОдноКлассники

        **Параметры**
            - **auth_key** : специальный ключ, который от игр вк или ОК нельзя никак сгенерировать
            или получить через какой-то запрос отдельно, поэтому, вам придется отслеживать
            запросы игры, и так получать его
            - **user_id** : айди вашего аккаунта ВК или OK
            - **session_key** : специальный ключ, если вы будете юзать ОК. Для вк оставляйте пустым
            - **client_type** : 1 = ВК, 2 = ОК
            - **websocket** : запускать ли сокет
            - **mobi** : телефон муд
            - **avatar** : ссылка на аватарку
            - **room_iders** : 1 - для публичных комнат, 10 - для приватных
        """
        self.auth_key = auth_key
        self.mobi = mobi
        self.viewer_id = user_id
        self.client_type = client_type
        self.session_key = session_key
        self.pc_fingerprint = "eb312822100c2618a3a608cd910dd131"
        self.api = "https://igra.love/web/"
        self.version = None
        self.data = None
        self.room_iders = room_iders
        self.get_boot_data(photo=avatar, first_name=first_name)
        Callbacks.__init__(self)
        SocketHandler.__init__(self, self)
        if websocket:
            self.create_connection()
        self.load_classes()

    def load_classes(self):
        self.user: User = User(self)
        self.room: Room = Room(self)
        self.viral: Viral = Viral(self)

    def handle_socket_message(self, data):
        self.resolve(data)

    def get_boot_data(self, first_name: str = "Игрок", last_name: str = "Игроков",
        photo: str = "", sex: int = 1) -> objects.BootData:
        data = {
            "fp": self.pc_fingerprint,
            "mobi": self.mobi,
            "first_name": first_name,
            "last_name": last_name,
            "photo_100": photo,
            "photo_200": photo,
            "sex": sex,
            "guests_limit": "1",
            "referrer": "library_zakovskiy"
        }
        if self.client_type == 2:
            data.update({
                "name_cases": f"{first_name},+,{first_name},+,{first_name},+,{first_name},+,{first_name},+",
                "update_name": "true",
                "ok_avatar_url": photo,
                "ok_fn": first_name,
                "ok_ln": last_name
            })
        else:
            data.update({
                "name_cases_json_array": json.dumps([first_name, first_name, first_name, first_name, first_name, first_name, first_name, first_name, first_name, first_name]),
                "user_id": self.viewer_id,
                "hash": ""
            })
        request = self.request("getBootData.php", "post", data)
        data = objects.BootData(request["data"]).BootData
        if request["code"] != 200:
            raise Exception(request)
        self.data = data
        self.version = data.version
        print(data.version)
        return data

    def ping_rooms(self, room_top: bool = True) -> dict:
        """ Получение обновлений о комнатах и рейтинге """
        return self.request("ping.php", _data={"room_top": room_top})

    def wheeloffortune_freespin_receive(self, id) -> dict:
        """ Получить подарочнoe бесплатное вращение от друга

        **Параметры**
            - **id** : айди подарка
        """
        return self.request("wheeloffortune/freespin/receive.php", _data={"id": id})

    def wheeloffortune_spin(self) -> dict:
        """ Крутануть фортуну """
        return self.request("wheeloffortune/spin.php")

    def wheeloffortune_freespin_send_spin(self, target_uid: int):
        """
        Отправить пользователю бесплатное вращение

        **Параметры**
            - **target_uid** : VK User ID
        """
        return self.request("wheeloffortune/freespin/sendSpin.php", _data={"target_uid": target_uid})

    def wheeloffortune_check_spins(self):
        """
        Получить кол-во вращений
        """
        return self.request("wheeloffortune/checkSpins.php")

    def send_private_message(self, text: str, target_uid: int, room_id: int,
        type: int = 50, free: bool = True) -> dict:
        """
        Отправить приватное сообщение пользователю

        **Параметры**
            - **text** : содержимое сообщения
            - **target_uid** : VK User ID, который состоит в руме
            - **room_id** : ID комнаты
            - **type** : какой-то тип сообщения
            - **free** : бесплатное ли это сообщение
        """
        data = {
            "text": text,
            "target_uid": target_uid,
            "room_id": f"{self.room_iders}_{room_id}",
            "free": free,
            "type": type
        }
        return self.request("privatemessage/add.php", _data=data)

    def money_box_get(self):
        return self.request("moneybox/get.php")

    def deposits_buy(self, target_uid: int, type: int = 1, force: int = 0):
        extra = self.md5(f"{self.viewer_id}_{force}_{target_uid}_{int(time.time())}_{self.version}")
        data = {
            "extra": extra,
            "target_uid": target_uid,
            "t": type,
            "f": force,
        }
        return self.request("deposits/buy.php", _data=data)

    def comment_add(self, target_uid: int, text: str, target_user_is_friend: bool = False, is_anonymous: bool = False):
        extra = self.md5(f"{self.viewer_id}_{target_uid}_{int(time.time())}_{self.version}")
        data = {
            "target_uid": target_uid,
            "text": text,
            "target_user_is_friend": target_user_is_friend,
            "is_anonymous": is_anonymous,
            "extra": extra
        }
        return self.request("comment/add.php", "post", _data=data)

    def comment_delete(self, comment_id, comment_owner_id):
        data = {
            "comment_id":comment_id,
            "comment_owner_id":comment_owner_id
        }
        return self.request("comment/delete.php", _data=data)

    def b8cb335(self, uids):
        return self.request("b8cb335.php", "post", {"uids": "_".join(uids)})

    def invitations_first_bonus(self, uids: str, extra: str):
        #extra = self.md5(f"{self.viewer_id}_{uids}_uids_{self.version}")
        data = {
            "_old": "sf7hf",
            "uids": uids,
            "extra": extra
        }
        result = self.request("invitations/first_bonus.php", "post", data)
        return result

    def invitations_bonus(self, target_uid):
        data = {
            "target_uid": target_uid
        }
        result = self.request("invitations/bonus.php", _data=data)
        return result

    def md5(self, string: str):
        m = hashlib.md5()
        m.update(string.encode())
        return m.hexdigest()

    def request(self, method, type: str = "get", _data: dir={}):
        _data.update({
            "ts": int(time.time()),
            "client_type": self.client_type
        })
        if self.client_type == 2:
            _data.update({
                "auth_sig": self.auth_key,
                "session_key": self.session_key,
                "logged_user_id": self.viewer_id
            })
        else:
            _data.update({
                "auth_key": self.auth_key,
                "api_id": 4333086,
                "viewer_id": self.viewer_id,
            })
        if type == "get":
            data = "?"
            for k in _data:
                data += f"&{k}={_data[k]}"
            result = requests.get(f"{self.api}{method}{data}").json()
        else:
            try:
                result = requests.post(f"{self.api}{method}", data=_data).json()
            except:
                result = requests.post(f"{self.api}{method}", data=_data).text
        return result
