#!/usr/bin/env python

import datetime
import logging
import os
import serial
import socket
import threading

from ConfigParser import SafeConfigParser



class Print:
    """Simple output class : print the frame"""

    def __init__(self, config):
        pass

    def got_frame(self, frame):
        print frame



class Gnuplot:
  """Simple Gnuplot output"""

  def __init__(self, config):
      self.config = config

  def got_frame(self, frame):
    date = frame['date'].strftime('%Y-%m-%d-%H:%M:%S')
    try:
        iinst = frame['IINST']
        isousc = frame['ISOUSC']
    except:
        return
    datafile = self.config.get('gnuplot', 'file')
    with open(datafile, 'a') as outfile:
        try:
            outfile.write('{} {} {}\n'.format(date, int(iinst), int(isousc)))
        except:
            logging.exception('Could not write to {}'.format(datafile))



class Mysql:
    """Output to a MySQL database"""
    ten_minutes = datetime.timedelta(minutes=10)
    one_hour = datetime.timedelta(hours=1)
    def __init__(self, config):
        import MySQLdb
        self.conn = MySQLdb.connect(host=config.get('mysql', 'host'),
                                    user=config.get('mysql', 'user'),
                                    passwd=config.get('mysql', 'password'),
                                    db=config.get('mysql', 'database'))
        # Calculate the current "10 minute step"
        now = datetime.datetime.now()
        self.period_start = now.replace(minute = now.minute / 10 * 10,
                                        second=0, microsecond=0)
        self.period_end = self.period_start + self.ten_minutes
        self.next_hour = now.replace(minute=0,second=0,microsecond=0)+self.one_hour
        self.reinit_data()

    def reinit_data(self):
        """Reinitialize the data, to be used when starting a new period"""
        self.period_data = {
                'tarif': '....',
                'subscribed_amperage': 0,
                'count': 0,
                'sum_of_all': 0,
                'min': 1000,
                'max': 0,
                'period': '....',
                'tomorrow': '....'
        }

    def got_frame(self, frame):
        """Make some calculation from a new frame and eventually store the result
        
        In order not to overload the database, averages are calculated instead
        of storing all received data
    
        A new frame is received every 1 or 2 seconds : 1 year of "real" data
        would represent 16 to 32 million entries in the database.
        An average on 10 minutes represents a little bit more than 52000 entries.
        """
        date = frame['date']
        try:    iinst = frame['IINST']
        except: iinst = False
        try:    isousc = frame['ISOUSC']
        except: isousc = False
        if date > self.period_end:
          self.switch_period()
        tarif = frame.get('OPTARIF', '....')
        # Periodic amperage
        self.period_data['tarif'] = tarif
        if isousc is not False:
            self.period_data['subscribed_amperage'] = int(isousc)
        self.period_data['count'] += 1
        if iinst is not False:
            current = int(iinst)
            self.period_data['sum_of_all'] += current
            if self.period_data['min'] > current:
                self.period_data['min'] = current
            if self.period_data['max'] < current:
                self.period_data['max'] = current
        self.period_data['period'] = frame.get('PTEC', '....')
        if tarif[:3] == 'BBR': self.period_data['tomorrow'] = frame.get(
                                                               'DEMAIN', '....')
        # Hourly counters
        if date > self.next_hour:
            if tarif == 'BASE':
                self.new_base_counter(frame.get('BASE', 0))
            elif tarif == 'HC..':
                self.new_hc_counters(frame.get('HCHP', 0), frame.get('HCHC', 0))
            elif tarif == 'EJP.':
                self.new_ejp_counters(frame.get('EJPHN', 0),
                                      frame.get('EJPHPM', 0))
            elif tarif[:3] == 'BBR':
                self.new_tempo_counters(tarif,
                                        frame.get('BBRHPJB', 0),
                                        frame.get('BBRHCJB', 0),
                                        frame.get('BBRHPJW', 0),
                                        frame.get('BBRHCJW', 0),
                                        frame.get('BBRHPJR', 0),
                                        frame.get('BBRHCJR', 0))
            self.next_hour = self.next_hour + self.one_hour
        
    def switch_period(self):
        """At the end of a period, send data to the database"""
        avg = self.period_data['sum_of_all'] / self.period_data['count']
        c = self.conn.cursor()
        c.execute(('INSERT INTO teleinfo_periodic_amperage '
                   '(datetime, tarif, subscribed_amperage, min_amperage, '
                   'avg_amperage, max_amperage, period, tomorrow) VALUES '
                   '(%s, %s, %s, %s, %s, %s, %s, %s)'),
                  (self.period_end.strftime('%Y-%m-%d %H:%M:%S'),
                   self.period_data['tarif'],
                   self.period_data['subscribed_amperage'],
                   self.period_data['min'], avg, self.period_data['max'],
                   self.period_data['period'], self.period_data['tomorrow'])
                 )
        self.conn.commit()
        self.reinit_data()
        self.period_start = self.period_end
        self.period_end = self.period_end + self.ten_minutes

    def new_base_counter(self, counter):
        c = self.conn.cursor()
        c.execute(('INSERT INTO teleinfo_hourly_counters '
                   '(datetime, tarif, base) VALUES (%s, %s, %s)'),
                  (self.next_hour.strftime('%Y-%m-%d %H:%M:%S'),
                   "BASE", counter)
                 )
        self.conn.commit()

    def new_hc_counters(self, hp, hc):
        c = self.conn.cursor()
        c.execute(('INSERT INTO teleinfo_hourly_counters '
                   '(datetime, tarif, hchp, hchc) VALUES (%s, %s, %s, %s)'),
                  (self.next_hour.strftime('%Y-%m-%d %H:%M:%S'),
                   "HC..", hp, hc)
                 )
        self.conn.commit()
    
    def new_ejp_counters(self, hn, hpm):
        c = self.conn.cursor()
        c.execute(('INSERT INTO teleinfo_hourly_counters '
                   '(datetime, tarif, ejphn, ejphpm) VALUES (%s, %s, %s, %s)'),
                  (self.next_hour.strftime('%Y-%m-%d %H:%M:%S'),
                   "EJP.", hn, hpm)
                 )
        self.conn.commit()

    def new_tempo_counters(self, tarif, hpjb, hcjb, hpjw, hcjw, hpjr, hcjr):
        c = self.conn.cursor()
        c.execute(('INSERT INTO teleinfo_hourly_counters '
                   '(datetime, tarif, bbrhpjb, bbrhcjb, bbrhpjw, '
                   'bbrhcjw, bbrhpjr, bbrhcjr) VALUES '
                   '(%s, %s, %s, %s, %s, %s, %s, %s)'),
                  (self.next_hour.strftime('%Y-%m-%d %H:%M:%S'),
                   tarif, hpjb, hcjb, hpjw, hcjw, hpjr, hcjr)
                 )
        self.conn.commit()



class Api:
    """Listen on the network for API requests"""
    def __init__(self, config):
        self.config = config
        self.data = {}
        self.lock = threading.Lock()
        thread = threading.Thread(target=self.api_listener, args=())
        thread.daemon = True
        thread.start()

    def got_frame(self, frame):
        date = frame['date']
        self.lock.acquire()
        for item in frame.items():
            self.data[item[0]] = (date, item[1])
        self.lock.release()

    def api_listener(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((self.config.get('api', 'ip'),self.config.getint('api', 'port')))
        s.listen(1)
        while True:
            conn, addr = s.accept()
            logging.debug('Connection from {} on port {}'.format(addr[0],
                                                                 addr[1]))
            if os.fork():
                conn.close()
            else:
                requested = conn.recv(8).strip()
                logging.debug('{} requested {}'.format(addr[0], requested))
                self.lock.acquire()
                if self.data.has_key(requested):
                    value = self.data[requested]
                    age = int((datetime.datetime.now() - \
                               value[0]).total_seconds())
                    logging.debug('Value for {} is {}, its age is {}'.format(
                                                     requested, value[1], age))
                    conn.send('{} {}'.format(value[1], age))
                else:
                    logging.debug('{} not found'.format(requested))
                    conn.send('Not Found')
                self.lock.release()
                conn.close()
                os._exit(0)



class Teleinfo:
    """The main class, containing the main loop"""
    def __init__(self, outputs, config):
        self.config = config
        self.serial = serial.Serial(port=config.get('main', 'device'),
                                    baudrate=1200, bytesize=serial.SEVENBITS,
                                    parity=serial.PARITY_EVEN,
                                    stopbits=serial.STOPBITS_ONE)
        self.outputs = []
        glob = globals()
        for method in outputs:
            classname = method.capitalize()
            if glob.has_key(classname):
                self.outputs.append(glob[classname](config))

    def run(self):
        """The main loop"""
        char = None
        line = ''
        frame = {'date': datetime.datetime.now()}
        # Wait for a frame end : the first incomplete frame is ignored
        while char != '\x03':
            char = self.serial.read(1)
        while True:
            char = self.serial.read(1)
            if char == '\x02': # Frame start
                frame = {'date': datetime.datetime.now()}
            elif char == '\x03': # Frame end
                for output in self.outputs:
                    output.got_frame(frame)
            elif char == '\n': # Line start
                line = ''
            elif char == '\r': # Line end
                newdata = self.parse_line(line)
                if newdata:
                    frame[newdata[0]] = newdata[1]
            else: # Any other character is part of a line
                line = line + char

    def parse_line(self, line):
        """Parse a data line, verify the checksum and return a (tag, data) checksum"""
        try:
            tag, data, checksum = line.split()
        except ValueError:
            return False
        checksum = ord(checksum)
        calculated = (sum(bytearray(tag+' '+data)) & 0x3f) + 0x20
        if checksum == calculated:
            return (tag, data)
        else:
            return False



# Daemon code largely inspired by http://code.activestate.com/recipes/278731/
# which is copyright (C) 2005 Chad J. Schroeder
def createDaemon(config):
   """Detach a process from the controlling terminal and run it in the
   background as a daemon.
   """
   try:
      pid = os.fork()
   except OSError, e:
      raise Exception, "%s [%d]" % (e.strerror, e.errno)
   if (pid == 0):
      os.setsid()
      try:
         pid = os.fork()
      except OSError, e:
         raise Exception, "%s [%d]" % (e.strerror, e.errno)
      if (pid == 0):
         os.chdir('/')
         os.umask(0)
         with open(config.get('main', 'pidfile'), 'w') as pidf:
           pidf.write(str(os.getpid()))
      else:
         os._exit(0)
   else:
      os._exit(0)
   os.close(0)
   os.close(1)
   os.close(2)
   os.open(os.devnull, os.O_RDWR)
   os.dup2(0, 1)
   os.dup2(0, 2)



if __name__ == '__main__':
    config = SafeConfigParser()
    config.read(['teleinfod.conf', os.path.expanduser('~/.teleinfod.conf'),
                 '/etc/teleinfod.conf', '/usr/local/etc/teleinfod.conf'])
    debugmode = config.getboolean('main', 'debug')
    logfile = config.get('main', 'logfile')
    logformat = '%(asctime)s - %(levelname)s - %(message)s'
    loglevel = logging.DEBUG if debugmode else logging.INFO
    logging.basicConfig(format=logformat, filename=logfile, level=loglevel)
    if config.getboolean('main', 'daemon'):
        logging.info('Starting detached, as a daemon')
        createDaemon(config)
    else:
        logging.basicConfig(format=logformat, level=loglevel)
        logging.info('Starting attached')

    outputs = [i.strip() for i in config.get('main', 'outputs').split(',')]

    try:
        Teleinfo(outputs, config).run()
    except:
        logging.exception('Something went wrong !')
