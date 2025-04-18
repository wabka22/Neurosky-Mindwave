using System;
using System.IO.Ports;
using System.Text;

class MindWaveReader
{
    static SerialPort serialPort;

    static void Main()
    {
        Console.OutputEncoding = Encoding.UTF8;
        Console.WriteLine("MindWave Reader");

        Console.WriteLine("Available COM ports:");
        string[] ports = SerialPort.GetPortNames();
        foreach (string port in ports)
        {
            Console.WriteLine("  " + port);
        }

        Console.Write("Enter MindWave COM port (e.g., COM3): ");
        string portName = Console.ReadLine();

        serialPort = new SerialPort(portName, 57600);
        serialPort.DataReceived += SerialPort_DataReceived;

        try
        {
            serialPort.Open();
            Console.WriteLine("Connected to MindWave");
            RequestData();
        }
        catch (Exception ex)
        {
            Console.WriteLine(" Connection error: " + ex.Message);
            return;
        }

        Console.ReadLine();
        serialPort.Close();
        Console.WriteLine("Connection closed.");
    }

    static void RequestData()
    {
        Console.WriteLine("Attempting to send data request");
        byte[] request = new byte[] { 0xAA };
        serialPort.Write(request, 0, request.Length);
        Console.WriteLine("Data request sent.");
    }

    static void SerialPort_DataReceived(object sender, SerialDataReceivedEventArgs e)
    {
        var sp = (SerialPort)sender;
        int bytesToRead = sp.BytesToRead;
        byte[] buffer = new byte[bytesToRead];
        sp.Read(buffer, 0, bytesToRead);

        ParseThinkGearStream(buffer);
    }

    static void ParseThinkGearStream(byte[] data)
    {
        for (int i = 0; i < data.Length; i++)
        {
            byte code = data[i];

            switch (code)
            {
                case 0x02:
                    if (i + 1 < data.Length)
                    {
                        Console.WriteLine($"[SIGNAL] POOR_SIGNAL: {data[i + 1]}");
                        i++;
                    }
                    break;

                case 0x04:
                    if (i + 1 < data.Length)
                    {
                        Console.WriteLine($"[eSense] ATTENTION: {data[i + 1]}");
                        i++;
                    }
                    break;

                case 0x05:
                    if (i + 1 < data.Length)
                    {
                        Console.WriteLine($"[eSense] MEDITATION: {data[i + 1]}");
                        i++;
                    }
                    break;

                case 0x03:
                    if (i + 1 < data.Length)
                    {
                        Console.WriteLine($"[HR] HEART_RATE: {data[i + 1]}");
                        i++;
                    }
                    break;

                case 0x81:
                    if (i + 32 < data.Length)
                    {
                        Console.WriteLine($"[EEG] EEG_POWER:");
                        for (int j = 0; j < 8; j++)
                        {
                            uint val = (uint)(
                                (data[i + 1 + j * 4] << 24) |
                                (data[i + 2 + j * 4] << 16) |
                                (data[i + 3 + j * 4] << 8) |
                                data[i + 4 + j * 4]);
                            Console.WriteLine($"  Band {j + 1}: {val}");
                        }
                        i += 32;
                    }
                    break;

                case 0x83:
                    if (i + 24 < data.Length)
                    {
                        Console.WriteLine($"[EEG] ASIC_EEG_POWER:");
                        for (int j = 0; j < 8; j++)
                        {
                            int offset = i + 1 + j * 3;
                            uint value = (uint)((data[offset] << 16) | (data[offset + 1] << 8) | data[offset + 2]);
                            Console.WriteLine($"  Band {j + 1}: {value}");
                        }
                        i += 24;
                    }
                    break;

                default:
                    break;
            }
        }
    }
}