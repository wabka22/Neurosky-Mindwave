import threading
import os
from typing import Tuple, Callable

import numpy as np
from time import sleep

from sklearn.decomposition import PCA
from sklearn.decomposition import FastICA

# Попытка импорта кастомного модуля Connector
try:
    from neurosky.connector import Connector
except ModuleNotFoundError:
    from connector import Connector

from rx3.internal import DisposedException
from rx3.subject import Subject
from rx3.operators import take_until_with_time


class Processor(object):
    def __init__(self, batch_mode: bool = False, live: bool = False):
        # Настраиваемые параметры
        self._is_live_recording: bool = live  # Режим "живой" записи
        self.data_resolution: int = 1  # Кол-во данных, необходимых для обработки
        self.blink_threshold: int = 50000000  # Порог отсечения всплесков (например, моргание)
        self.recorded_data: list[int] = []  # Хранилище записанных данных
        self.is_recording: bool = False  # Флаг записи
        self._is_open: bool = True  # Флаг активности
        self._sample_frequency: int = 512  # Частота дискретизации
        self.batch_mode: bool = batch_mode  # Пакетный режим
        self.processed_data: list[int] = []  # Обработанные данные

        # Хранилище для объектов-подписок
        self.subscriptions: list[Subject] = []

        # Субъект для передачи данных подписчикам
        self.data: Subject = Subject()
        self.subscriptions.append(self.data)

        # Скрытые параметры
        self._raw_data_batch: list[int] = []  # Буфер необработанных данных
        self._save_path: str = ''  # Путь для сохранения данных

        split: int = 50  # Кол-во компонент в PCA/ICA

        # Инициализация PCA и ICA
        self._pca = PCA(
            n_components=split,
            whiten=False,
        )
        self._ica = FastICA(
            n_components=split,
            tol=1
        )

    # Метод запуска функции в отдельном потоке
    @staticmethod
    def _init_thread(target: Callable, args: Tuple = ()) -> None:
        threading.Thread(target=target, args=args).start()

    # Добавление нового значения (в режиме реального времени)
    def add_data(self, raw_data: int):
        if not self.batch_mode:
            self._raw_data_batch.append(raw_data)
            if len(self._raw_data_batch) >= self.data_resolution and self._is_open:
                self._init_thread(target=self._fft)

    # Метод обработки сразу пакета данных (batch mode)
    def fft(self, data_batch):
        if self.batch_mode:
            for data in data_batch:
                self._raw_data_batch.append(data)
            self._fft()

    # Установка частоты дискретизации
    def set_sampling_rate(self, fs: int) -> None:
        self._sample_frequency = fs

    # Метод обработки данных через FFT
    def _fft(self) -> None:
        temp_data_batch = self._raw_data_batch.copy()
        self._raw_data_batch: list[int] = []
        batch_size: int = len(temp_data_batch)
        print(batch_size)
        # Фильтрация морганий/всплесков
        if batch_size != 0 and (
            self.blink_threshold > np.amax(temp_data_batch) or -self.blink_threshold < np.amin(temp_data_batch)
        ):
            x_fft = np.fft.rfftfreq(batch_size, 2 * (1 / self._sample_frequency))  # Частотная ось
            if self._is_live_recording:
                slice_size: int = 48  # Для живого режима ограничиваем до 48 Гц
            else:
                # В противном случае — выбираем с округлением вниз
                slice_size: int = round(len(list(filter(lambda x: x < 50, x_fft))), -1)

            x_fft = x_fft[:slice_size]  # Ограничиваем по срезу
            y_fft = np.absolute(np.real(np.fft.rfft(temp_data_batch)))[:slice_size]  # Амплитуды
            self.processed_data = np.array([x_fft, y_fft])[1]  # Сохраняем только амплитуду
            self.data.on_next(self.processed_data)  # Передаём обработанные данные подписчикам

    # Преобразование данных с помощью PCA
    def pca(self, x: int):
        x = (x - np.mean(x, axis=0)) / np.std(x, axis=0)  # Нормализация
        a = self._pca.fit_transform(x)
        return a

    # Преобразование данных с помощью ICA
    def ica(self, x: int):
        x = (x - np.mean(x, axis=0)) / np.std(x, axis=0)  # Нормализация
        return self._ica.fit_transform(x)

    # Метод записи данных в файл
    def record(self, path: str = './processor_data', recording_length: int = 10) -> None:
        if not self.is_recording:
            self._save_path = os.path.realpath(path)
            self.recorded_data = []
            self.is_recording = True
            # Подписываемся на поток данных на фиксированное время
            self.data.pipe(take_until_with_time(recording_length)).subscribe(
                observer=lambda values: self.recorded_data.append(values),
                on_error=lambda e: print(e),
                on_completed=self._save
            )
        else:
            print('Уже идёт запись...')

    # Сохранение записанных данных в .npy файл
    def _save(self) -> None:
        np.save(self._save_path, self.recorded_data)
        self.is_recording = False
        print('Запись завершена')

    # Метод для корректного завершения обработки
    def close(self) -> None:
        self._is_open = True
        sleep(1.5)
        for subscription in self.subscriptions:
            try:
                subscription.dispose()
            except DisposedException:
                pass
        print('Processor завершил работу')

    # Поддержка контекстного менеджера (with Processor() as p:)
    def __enter__(self) -> ['Processor']:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
