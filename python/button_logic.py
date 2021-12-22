import threading
import time
from threading import Thread

from telegram import Update

from constants import Constants
from hardware import Hardware
from image import print_message
from printer import Printer
from recording import Recording
from tg import Telegram


class ButtonLogic:

    def __init__(self, hardware: Hardware, tg: Telegram, rec: Recording):
        self.hw = hardware
        self.tg = tg
        self.rec = rec
        self.is_recording = False
        self.destination = None
        self.sos_starts_at = None
        self.is_sos = False
        self.sos_thread: Thread = None
        self.reset_destination_at = None
        self.reset_thread = Thread(target=self._reset_thread_proc)
        self.reset_thread.setDaemon(True)
        self.reset_thread.start()


    def _reset_thread_proc(self):
        while True:
            time.sleep(0.1)
            if self.is_recording or self.is_sos or self.reset_destination_at is None:
                continue
            if time.time() > self.reset_destination_at:
                self.destination = None
                self.reset_destination_at = None
                self.update_destination()


    def record(self):
        try:
            if self.destination is None:
                for i in range(4):
                    self.hw.led(Hardware.Led(Hardware.Led.Dir1.value + i), Hardware.LedMode.Blink)
                while self.hw.btn_pressed(Hardware.Buttons.Rec):
                    time.sleep(0.001)
                self.hw.all_volatile_leds_off()
                return

            self.hw.led(Hardware.Led.Rec, Hardware.LedMode.On)
            self.hw.led(Hardware.Led(Hardware.Led.Dir1.value + self.destination), Hardware.LedMode.Blink)
            audio = self.rec.record()
            self.hw.led(Hardware.Led.Rec, Hardware.LedMode.Blink)
            self.hw.led(Hardware.Led(Hardware.Led.Dir1.value + self.destination), Hardware.LedMode.Off)
            try:
                self.tg.send_audio(audio, self.destination)
            except:
                Printer(self.hw).print_img(print_message("Ошибка", "Не удалось отправить сообщение!"), 6000, 1)
            finally:
                self.hw.led(Hardware.Led.Rec, Hardware.LedMode.Off)
                self.hw.led(Hardware.Led(Hardware.Led.Dir1.value + self.destination), Hardware.LedMode.On)

        finally:
            self.is_recording = False

    def start_sos(self):
        self.is_sos = True
        for i in range(4):
            self.tg.send_text(Constants.SOS_MESSAGE, i)
        self.hw.led(Hardware.Led.Sos, Hardware.LedMode.On)
        self.hw.led(Hardware.Led.Dir1, Hardware.LedMode.Blink)
        self.hw.led(Hardware.Led.Dir2, Hardware.LedMode.Blink)
        self.hw.led(Hardware.Led.Dir3, Hardware.LedMode.Blink)
        self.hw.led(Hardware.Led.Dir4, Hardware.LedMode.Blink)
        self.hw.buzz(130, 150, 200, 2)

    def on_tg_stopsos(self, update: Update):
        if (self.sos_starts_at is None and not self.is_sos):
            update.message.reply_text("Режим SOS не активен")
            return
        update.message.reply_text("Отменяю SOS")
        self.cancel_sos()

    def cancel_sos(self):
        self.sos_starts_at = None
        if self.is_sos:
            self.is_sos = False

            def _spawn_me():
                for i in range(4):
                    self.tg.send_text(Constants.SOS_CANCELLED_MESSAGE, i)

            Thread(target=_spawn_me).start()
        self.hw.all_volatile_leds_off()
        self.destination = None
        self.hw.buzz(100, 120, 5, 2)

    def on_sos(self):
        if self.is_recording and not self.is_sos:
            return

        if self.sos_starts_at is not None:
            self.cancel_sos()
            return
        self.hw.led(Hardware.Led.Sos, Hardware.LedMode.Blink)
        self.hw.led(Hardware.Led.Dir1, Hardware.LedMode.On)
        self.hw.led(Hardware.Led.Dir2, Hardware.LedMode.On)
        self.hw.led(Hardware.Led.Dir3, Hardware.LedMode.On)
        self.hw.led(Hardware.Led.Dir4, Hardware.LedMode.On)
        self.hw.led(Hardware.Led.Rec, Hardware.LedMode.Off)
        self.hw.buzz(100, 130, Constants.SOS_TIME_DELAY*10, 2)
        self.sos_starts_at = time.time() + Constants.SOS_TIME_DELAY
        def _thread_proc():
            while self.sos_starts_at is not None and time.time() < self.sos_starts_at:
                time.sleep(0.1)
            if self.sos_starts_at is None:
                return
            self.start_sos()
        self.sos_thread = threading.Thread(target=_thread_proc)
        self.sos_thread.setDaemon(True)
        self.sos_thread.start()

    def reset_reset_timer(self):
        self.reset_destination_at = time.time() + Constants.DESTINATION_RESET_SECONDS

    def update_destination(self):
        self.hw.all_volatile_leds_off()
        if self.destination is not None:
            self.hw.led(Hardware.Led(Hardware.Led.Dir1.value + self.destination), Hardware.LedMode.On)

    def on_btn_click(self, btn: Hardware.Buttons):
        if self.is_recording:
            return
        if btn == Hardware.Buttons.Rec:
            self.is_recording = True
            Thread(target=self.record, daemon=True).start()
            return
        if btn == Hardware.Buttons.Sos:
            self.on_sos()
            return
        if btn == Hardware.Buttons.Dir1:
            self.destination = 0
        if btn == Hardware.Buttons.Dir2:
            self.destination = 1
        if btn == Hardware.Buttons.Dir3:
            self.destination = 2
        if btn == Hardware.Buttons.Dir4:
            self.destination = 3
        self.update_destination()
        self.reset_reset_timer()



