import threading
import socket
from typing import Callable, Tuple
import numpy as np
import os
from json import loads
from time import sleep
from math import floor
from rx3.internal import DisposedException
from rx3.subject import Subject
from rx3.operators import take_until_with_time

class Connector(object):
    def __init__(self, debug: bool = False, verbose: bool = False, hostname: str = '127.0.0.1', port: int = 13854) -> None:
        """
        Конструктор класса Connector.
        :param debug: Использовать ли отладочный режим (генерация случайных данных вместо подключения к устройству).
        :param verbose: Выводить ли подробную информацию в консоль.
        :param hostname: IP-адрес или хостнейм сервера (по умолчанию локальный).
        :param port: Порт подключения.
        """
        self._DEBUG = debug
        self._VERBOSE = verbose
        self._HOSTNAME = hostname
        self._PORT = port

        # Список подписок для последующего отключения
        self.subscriptions: list[Subject] = []

        # Наблюдаемые потоки (Subjects)
        self.data: Subject = Subject()
        self.subscriptions.append(self.data)

        self.poor_signal_level: Subject = Subject()
        self.subscriptions.append(self.poor_signal_level)

        self.sampling_rate: Subject = Subject()
        self.subscriptions.append(self.sampling_rate)

        # Скрытые параметры
        self._sampling_rate_counter: int = 0
        self._is_open: bool = True
        self._save_path: str = ''

        # Параметры записи
        self.is_recording: bool = False
        self.recorded_data: list[int] = []

        # Создание TCP сокета
        self.client_socket: socket.socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)

    def start(self):
        """
        Запускает поток генерации данных.
        """
        self._init_thread(target=self._generate_data)

    @staticmethod
    def _init_thread(target: Callable, args: Tuple = ()) -> None:
        """
        Запускает целевую функцию в новом потоке.
        """
        threading.Thread(target=target, args=args).start()

    def _generate_sampling_rate(self) -> None:
        """
        Поток, обновляющий частоту дискретизации каждую секунду.
        """
        while self._is_open:
            self._sampling_rate_counter = 0
            sleep(1)
            self.sampling_rate.on_next(self._sampling_rate_counter)

    def _generate_data(self) -> None:
        """
        Основной поток генерации или получения данных.
        В зависимости от флага DEBUG либо генерирует данные, либо подключается к сокету и читает поток от устройства.
        """
        if self._DEBUG:
            self._init_thread(target=self._generate_sampling_rate)
            while self._is_open:
                # Генерация случайного значения с нормальным распределением
                gaussian_num = floor(np.random.normal(0, 150, 1)[0])
                if -150 < gaussian_num < 150:
                    self.data.on_next(gaussian_num)
                    self.poor_signal_level.on_next(np.random.randint(0, 100))
                    self._sampling_rate_counter += 1
                    sleep(0.00001)
        else:
            try:
                # Подключение к сокету
                self.client_socket.connect((self._HOSTNAME, self._PORT))
                # Отправка конфигурационного JSON
                self.client_socket.sendall(bytes('{"enableRawOutput":true,"format":"Json"}'.encode('ascii')))
                self._init_thread(target=self._generate_sampling_rate)

                if self._VERBOSE:
                    print('Retrieving data...')

                while self._is_open:
                    raw_bytes = self.client_socket.recv(1000)
                    data_set = (str(raw_bytes)[2:-3].split(r'\r'))
                    for data in data_set:
                        self._sampling_rate_counter += 1
                        try:
                            json_data = loads(data)
                            try:
                                # Если есть поле rawEeg — получаем сигнал
                                temp_data = json_data['rawEeg']
                                self.data.on_next(temp_data)
                            except:
                                # Если нет — пробуем получить уровень сигнала
                                if len(json_data) > 3:
                                    self.poor_signal_level.on_next(json_data['eSense']['poorSignalLevel'])
                                else:
                                    self.poor_signal_level.on_next(json_data['poorSignalLevel'])
                        except:
                            continue
                    if self.poor_signal_level == 200 and self._VERBOSE:
                        print('Poor Connections!')
            except (ConnectionError, ConnectionRefusedError, ConnectionAbortedError, ConnectionResetError):
                print('An error connection occurred, are you connected?')
                self.close()
                raise ConnectionError('An error connection occurred, are you connected?')

    def record(self, path='./connector_data', recording_length=10) -> None:
        """
        Начинает запись данных в течение заданного времени и сохраняет в файл.
        """
        if not self.is_recording:
            self._save_path = os.path.realpath(path)
            self.recorded_data = []
            self.is_recording = True
            self.data.pipe(take_until_with_time(recording_length)).subscribe(
                observer=lambda value: self.recorded_data.append(value),
                on_error=lambda e: print(e),
                on_completed=self._save
            )
        else:
            print('Already recording...')

    def _save(self) -> None:
        """
        Сохраняет записанные данные в .npy файл.
        """
        np.save(self._save_path, self.recorded_data)
        self.is_recording = False
        print('Recording Complete')

    def await_recording(self) -> None:
        """
        Ожидает завершения записи.
        """
        while self.is_recording:
            pass

    def close(self) -> None:
        """
        Завершает работу, закрывает сокет и отписывает всех подписчиков.
        """
        self._is_open = False
        self.is_recording = False
        sleep(1.5)  # Ждём завершения потоков

        for subscription in self.subscriptions:
            try:
                subscription.dispose()
            except DisposedException:
                pass
        try:
            self.client_socket.close()
        finally:
            print('Connection Closed!')

    def __enter__(self):
        """
        Поддержка with-контекста.
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Завершение работы в with-контексте.
        """
        self.close()


