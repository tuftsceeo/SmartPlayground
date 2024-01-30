import os, sys
import subprocess
from subprocess import Popen, PIPE
import time

#resources file for EDL jupyter notebooks
#2023A

#hides console output for some gopigo methods that like to be very verbose
class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

def stop_speaking_ip():        
    switch_to_pi()
    stop_speaking_ip_helper()
    time.sleep(1)
    stop_speaking_ip_helper()
    time.sleep(1)
    switch_to_jupyter()
    print('Pi is not speaking its ip address, restart the pi to have it speak the address again.')
    
#stops the pi from speaking its ip all the time
def stop_speaking_ip_helper():
    #switch_to_pi()
    cmd=['ps','aux']
    output=subprocess.Popen(cmd,stdout=subprocess.PIPE).communicate()
    output=str(output[0]).split('\\n')
    processesToKill=[]
    for p in output:
        if 'aud.sh'  in p: #this is the file that makes it speak its ip
            processesToKill.append(p)
    if len(processesToKill)>0: #if it is running
        for p in processesToKill:
            info = p.split(' ') #kill all of its processes
            for entry in info:
                if entry.isdigit():
                    sudoPassword = 'jupyter'
                    p = Popen(['sudo', 'kill', entry], stdin=PIPE, stderr=PIPE, universal_newlines=True)
                    time.sleep(1)
                    sudo_prompt = p.communicate(sudoPassword + '\n')[1]
                    # os.system('kill %d'%(int(entry)))
                    break
        #print('Pi is no longer speaking its ip address, restart the pi to have it speak the address again.')
        #switch_to_jupyter()
    #else:
        #continue
        #print('Pi is not speaking its ip address, restart the pi to have it speak the address again.')
        #switch_to_jupyter()

def switch_to_pi():
    sudoPassword = 'robots1234'
    command = 'su pi'.split()
    p = Popen(['sudo', '-S'] + command, stdin=PIPE, stderr=PIPE, universal_newlines=True)
    sudo_prompt = p.communicate(sudoPassword + '\n')[1]

def switch_to_jupyter():
    sudoPassword = 'jupyter'
    command = 'su jupyter'.split()
    p = Popen(['sudo', '-S'] + command, stdin=PIPE, stderr=PIPE, universal_newlines=True)
    sudo_prompt = p.communicate(sudoPassword + '\n')[1]

#shuts down pi
def shutdown_pi():
    subprocess.Popen(['sudo','shutdown','-h','now'])
    
import re
    
def add_new_wifi():
    switch_to_jupyter()

    ssid = input("Provide your wifi SSID (e.g. the name) then press enter: ")
    pwd = input("Provide your wifi password then press enter: ")
    command = ['sudo', 'sh', '-c', "wpa_passphrase %s %s >> /etc/wpa_supplicant/wpa_supplicant.conf"%(ssid, pwd)]

    cmd1 = Popen(command, shell = False, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    #output = cmd1.stdout.read()
    #print(output)
    time.sleep(1)
    #sudo_prompt = cmd1.communicate(sudo_password  + '\n')[1]
    #print(sudo_prompt)
    

def read_known_wifi():
    command = ['cat', "/etc/wpa_supplicant/wpa_supplicant.conf"]
    cmd2 = Popen(command, shell = False, universal_newlines=True, stdout=PIPE)
    output = cmd2.stdout.read() 
    output = re.split('network=', output)
    for new_net in output[::-1]:
        if "ssid" in new_net:
            new_net = re.sub(r'[\{\}\t]', '', new_net).strip(' \n\t').split()
            print("===========")
            for detail in new_net:
                if "ssid" in detail or "psk" in detail:
                    print(detail)