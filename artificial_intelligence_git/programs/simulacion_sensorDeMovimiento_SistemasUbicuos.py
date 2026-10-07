import random
import time

def simular_sensor_movimiento():
    luces_encendidas = False

    print("--- Simulador de Sensor de Movimiento (Sistemas Ubicuos) ---")
    print("Presiona Ctrl+C para detener la simulación.\n")

    try:
        while True:
            # Genera 0 (sin movimiento) o 1 (movimiento detectado)
            lectura_sensor = random.choice([0, 1])

            # Detecta presencia de persona
            if lectura_sensor == 1 and not luces_encendidas:
                luces_encendidas = True
                print("[ALERTA]: Movimiento detectado -> Luces encendidas")

            # Detecta ausencia de persona
            elif lectura_sensor == 0 and luces_encendidas:
                luces_encendidas = False
                print("[ALERTA]: Sin movimiento -> Luces apagadas")

            # Espera 2 segundos antes de la siguiente lectura
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nSimulación finalizada.")

if __name__ == "__main__":
    simular_sensor_movimiento()
