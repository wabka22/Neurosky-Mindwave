#include <windows.h>
#include <iostream>
#include <vector>
#include <cstdint>
#include <locale>
#include <codecvt>

void sendData(HANDLE hSerial, const std::string& data) {
    DWORD bytesWritten;
    WriteFile(hSerial, data.c_str(), data.size(), &bytesWritten, NULL);
}

std::vector<uint8_t> readData(HANDLE hSerial) {
    uint8_t buffer[256];
    DWORD bytesRead;
    std::vector<uint8_t> data;
    
    if (ReadFile(hSerial, buffer, sizeof(buffer), &bytesRead, NULL) && bytesRead > 0) {
        data.insert(data.end(), buffer, buffer + bytesRead);
    }
    return data;
}

bool isValidPacket(const std::vector<uint8_t>& data) {
    return data.size() > 2 && data[0] == 0xAA && data[1] == 0xAA;
}

int main() {
    SetConsoleOutputCP(CP_UTF8);  // Устанавливаем UTF-8 для консоли

    const char* portName = "COM4";  // Укажи свой порт

    HANDLE hSerial = CreateFileA(portName, GENERIC_READ | GENERIC_WRITE, 0, 0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    if (hSerial == INVALID_HANDLE_VALUE) {
        std::cerr << u8"Ошибка открытия порта!\n";
        return 1;
    }

    DCB serialParams;
    ZeroMemory(&serialParams, sizeof(serialParams));
    serialParams.DCBlength = sizeof(serialParams);

    if (!GetCommState(hSerial, &serialParams)) {
        std::cerr << u8"Ошибка получения параметров COM-порта!\n";
        CloseHandle(hSerial);
        return 1;
    }

    serialParams.BaudRate = CBR_9600;  // MindWave использует 9600 бод
    serialParams.ByteSize = 8;
    serialParams.StopBits = ONESTOPBIT;
    serialParams.Parity = NOPARITY;
    serialParams.fRtsControl = RTS_CONTROL_ENABLE; // Включаем RTS/CTS

    SetCommState(hSerial, &serialParams);
    std::cout << u8"Соединение установлено!\n";

    while (true) {
        std::vector<uint8_t> response = readData(hSerial);
        if (!response.empty() && isValidPacket(response)) {
            std::cout << u8"MindWave передал " << response.size() << u8" байт\n";
        }
        Sleep(100);
    }

    CloseHandle(hSerial);
    return 0;
}
