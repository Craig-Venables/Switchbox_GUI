import serial
import serial.tools.list_ports as list_ports
import time


class Switchbox:
    def __init__(self):
        #Initiallise serial connection with the arduino
        baud_rate = 9600
        port = self.getPort()

        self.ser = serial.Serial(port, baud_rate, timeout=1)

        #define array to hold devices to switch
        self.relays_to_switch = []

        self.status = "idle"
        self.running = False

        self.connected = False
        
        while not self.connected:
            msg = self.getMessage()

            if msg == "Send 'READY' to begin input array reception.":
                self.connected = True
    
    def close(self):
        self.running = True

        while self.running and self.connected:
            if self.status == "idle":
                self.status = self.beginComms()

            elif self.status == "ready":
                while self.ser.in_waiting > 0:
                    message = self.getMessage()

                    if message == "READY RECIEVED":
                        self.resetRelays()

                        time.sleep(0.8)

        if self.ser and self.ser.is_open:
            self.ser.close()

    def getPort(self):
        ports = list_ports.comports()
        arduino_port_info = "USB VID:PID=2341:0042"
        
        for port in ports:
            #extract port info
            hwid = port.hwid

            if arduino_port_info in hwid:
                #check for arduino in port info and return name
                port = port.name
                return port
            
    def setShiftRegisters(self):
        command = "SET_REGISTERS"
        self.sendMessage(command)
    

    def resetRelays(self):
        print("Resetting all shift registers...\n")
        command = "RESET"
        self.sendMessage(command)
        

    def getMessage(self,print_msg = True):
        msg = self.ser.read_until().decode().strip()
        if print_msg:
            print(f"Received: {msg}")
        return(msg)
    

    def sendMessage(self, msg, print_msg = True):
        self.ser.write(msg.encode())
        if print_msg:
            print(f"Sent: {msg}")


    def beginComms(self, chosen_relays = []):           
        self.sendMessage('READY\n')

        if chosen_relays:
            for relay in chosen_relays:
                if (relay > 0) and (relay < 111):
                    self.relays_to_switch.append(relay-1)
                    print(self.relays_to_switch)

                else:
                    print("relay out of bounds, please choose a valid index\n\n")
        else:
            print("No relays selected")
            
        return("ready")

        
    def sendInput(self):
        finished = False
        instruction = "WAIT"
        while not finished:
            while instruction == "WAIT":
                message = self.getMessage()

                if message == "GIVE_NUM":
                    instruction = "SEND_NUM"
            
            if instruction == "SEND_NUM":
                self.sendMessage(str(len(self.relays_to_switch)))
                time.sleep(0.8)
                self.getMessage()

                self.sendMessage("START_RCV\n")
                time.sleep(0.8)
                instruction = "SEND_RELAYS"
                
            #debug = input("continue?")
            while instruction == "SEND_RELAYS":
                message = self.getMessage()

                if message == "GIVE_RELAYS":
                
                    for relay_index in self.relays_to_switch:
                        self.sendMessage((str(relay_index) + "\n"), print_msg = False)
                        time.sleep(0.1)
                
                    instruction = "FINALISE"

            while instruction == "FINALISE":
                time.sleep(1)
                message = self.getMessage()

                if message == "RELAYS_RECIEVED":
                    print("relay indices transmitted")
                    time.sleep(0.8)

                    command = "MK_ARRAY\n"
                    self.sendMessage(command)
                    
                    instruction = "FINISHED"
            
            if instruction == "FINISHED":
                print("finished transmission")
                finished = True
        

    def activate(self, relays = [1,10]):
        self.running = True

        while self.running and self.connected:
            if self.status == "idle":
                self.status = self.beginComms(relays)

            elif self.status == "ready":
                while self.ser.in_waiting > 0:
                    message = self.getMessage()
                    
                    if message == "READY RECIEVED":
                        self.sendMessage("START")

                        time.sleep(0.8)

                    if message == "SEND ARRAY":
                        self.sendInput()
                        time.sleep(0.8)

                    if message == "ARRAY RECEIVED":
                        time.sleep(0.8) 
                        self.setShiftRegisters()
                        
                    if message == "FINISHED":
                        self.sendMessage("IDLE")
                        self.status = "idle"

                        self.relays_to_switch = []
                        self.running = False


if __name__ == "__main__":
    box = Switchbox()
    
    # Run interactive test
    box.activate([1,2])
    
    # Or manual control
    # box.set_relays([0, 1, 2])  # 0-based indexes
    # box.activate()
    input("close connection (enter)")
    box.close()