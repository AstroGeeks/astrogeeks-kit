import abc
import sys
import collections
import datetime
import asyncio
import logging
import collections

logger = logging.getLogger("AstroPlant")

class PeripheralManager(object):
    """
    A peripheral device manager; this manager keeps track of all peripherals,
    provides the ability to subscribe to peripheral device measurements,
    and provides the ability to run all runnable peripheral devices (such as
    sensors).
    """

    def __init__(self):
        self.peripherals = []
        self.subscribers = []
        self.busy = 0

    def runnable_peripherals(self):
        """
        :return: An iterable of all runnable peripherals.
        """
        return filter(lambda peripheral: peripheral.RUNNABLE, self.peripherals)

    async def run(self):
        """
        Run all runnable peripherals.
        """
        await asyncio.wait([peripheral.run() for peripheral in self.runnable_peripherals()])

    def subscribe_physical_quantity(self, physical_quantity, callback):
        """
        Subscribe to messages concerning a specific physical quantity.

        :param physical_quantity: The name of the physical quantity for which the measurements are being subscribed to.
        :param callback: The callback to call with the measurement.
        """
        self.subscribe_predicate(lambda measurement: measurement.get_physical_quantity() == physical_quantity, callback)

    def subscribe_predicate(self, predicate, callback):
        """
        Subscribe to messages that conform to a predicate.

        :param predicate: A function taking as input a measurement and returning true or false.
        :param callback: The callback to call with the measurement.
        """
        self.subscribers.append((predicate, callback))

    def _publish_handle(self, measurement):
        """
        Publish a measurement.

        :param measurement: The measurement to publish.
        """
        for (predicate, callback) in self.subscribers:
            if predicate(measurement):
                callback(measurement)

    def create_peripheral(self, peripheral_class, peripheral_object_name, peripheral_parameters):
        """
        Create and add a peripheral by its class name.

        :param peripheral_class: The class of the peripheral to add.
        :param peripheral_object_name: The name of the specific peripheral to add.
        :param peripheral_parameters: The instantiation parameters of the peripheral.
        :return: The created peripheral.
        """

        # Instantiate peripheral
        peripheral = peripheral_class(peripheral_object_name, self, **peripheral_parameters)

        # Set message publication handle
        peripheral._set_publish_handle(self._publish_handle)

        self.peripherals.append(peripheral)

        return peripheral

class Peripheral(object):
    """
    Abstract peripheral device base class.
    """

    #: Boolean indicating whether the peripheral is runnable.
    RUNNABLE = False

    #: Boolean indicating whether the peripheral can accept commands.
    COMMANDS = False

    def __init__(self, name, peripheral_device_manager):
        self.name = name
        self.manager = peripheral_device_manager
        self.logger = logger.getChild("peripheral").getChild(self.name)

    @abc.abstractmethod
    async def run(self):
        """
        Asynchronously run the peripheral device.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def do(self, command):
        """
        Asynchronously perform a command on the device.
        """
        raise NotImplementedError()

    def get_name(self):
        return self.name

    def _set_publish_handle(self, publish_handle):
        """
        Set the handle this device's measurements should be published to.
        """
        self._publish_handle = publish_handle

    def __str__(self):
        return self.name
        
class Sensor(Peripheral):
    """
    Abstract sensor base class.
    """

    RUNNABLE = True

    #: Amount of time in seconds to wait between making measurements
    TIME_SLEEP_BETWEEN_MEASUREMENTS = 5.0

    #: Amount of time in seconds over which measurements are reduced before publishing them for storage
    TIME_REDUCE_MEASUREMENTS = 60.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.measurements = []

    async def run(self):
        await asyncio.wait([self._make_measurements(), self._reduce_measurements()])

    async def _make_measurements(self):
        """
        Repeatedly make measurements.
        """
        while True:
            measurement = await self.measure()
            if isinstance(measurement, collections.Iterable):
                # Add all measurements to the sensor's measurement list (for later reduction)
                self.measurements.extend(measurement)
            else:
                # Add measurement to the sensor's measurement list (for later reduction)
                self.measurements.append(measurement)
            await asyncio.sleep(self.TIME_SLEEP_BETWEEN_MEASUREMENTS)

    async def _reduce_measurements(self):
        """
        Repeatedly reduce multiple measurements made to a single measurement.
        """
        while True:
            self.logger.debug("Reducing measurements. %s" % len(self.measurements))

            # Group measurements by physical quantity and unit
            grouped_measurements = collections.defaultdict(list)
            for measurement in self.measurements:
                grouped_measurements[(measurement.get_physical_quantity(), measurement.get_physical_unit())].append(measurement)

            # Empty list
            self.measurements = []

            # Produce list of reduced measurements
            try:
                reduced_measurements = [self.reduce(val) for (key, val) in grouped_measurements.items()]
            except Exception as e:
                self.logger.error("Could not reduce measurements: %s" % e)
                return

            # Publish reduced measurements
            for reduced_measurement in reduced_measurements:
                asyncio.ensure_future(self._publish_measurement(reduced_measurement))

            await asyncio.sleep(self.TIME_REDUCE_MEASUREMENTS)

    @abc.abstractmethod
    async def measure(self):
        raise NotImplementedError()

    async def _publish_measurement(self, measurement):
        self._publish_handle(measurement)

    def reduce(self, measurements):
        """
        Reduce a list of measurements to a single measurement.

        :param measurements: The list of measurements to reduce.
        :return: A single measurement, or None
        """
        if not measurements:
            return None

        values = list(map(lambda m: m.get_value(), measurements))
        avg_value = sum(values) / len(values)

        # Make a new measurement based on the old measurements
        measurement = measurements[0]
        return Measurement(measurement.get_peripheral(), measurement.get_physical_quantity(), measurement.get_physical_unit(), avg_value, measurement_type = MeasurementType.REDUCED)

class Actuator(Peripheral):
    """
    Abstract actuator base class. Incomplete.
    """

    RUNNABLE = False
    
        
class MeasurementType(object):
    """
    Class holding the possible types of measurements.
    """

    #: A real-time measurement
    REAL_TIME = "REAL_TIME"

    #: A reduced measurement (e.g. an average over a longer time window)
    REDUCED = "REDUCED"

class Measurement(object):
    """
    Measurement class.
    """

    def __init__(self, peripheral, physical_quantity, physical_unit, value, measurement_type=MeasurementType.REAL_TIME):
        self.peripheral = peripheral
        self.physical_quantity = physical_quantity
        self.physical_unit = physical_unit
        self.value = value
        self.date_time = datetime.datetime.utcnow()
        self.measurement_type = measurement_type

    def get_peripheral(self):
        return self.peripheral

    def get_physical_quantity(self):
        return self.physical_quantity

    def get_physical_unit(self):
        return self.physical_unit

    def get_value(self):
        return self.value

    def get_date_time(self):
        return self.date_time

    def get_measurement_type(self):
        return self.measurement_type

    """
    def dict(self):
        return {
            'peripheral': self.peripheral,
            'physical_quantity': self.physical_quantity,
            'physical_unit': self.physical_unit,
            'value': self.value,
            'date_time': self.date_time,
            'measurement_type': self.measurement_type
        }
    """
        
    def __str__(self):
        return "%s - %s %s: %s %s" % (self.date_time, self.peripheral, self.physical_quantity, self.value, self.physical_unit)

class Display(Actuator):
    """
    An abstract class for peripheral display devices. These devices can display strings.

    Todo: improve implementation, and add ability to somehow "rotate" messages, e.g. showing
    up-to-date measurement statistics.
    """

    RUNNABLE = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_message_queue = []

    async def run(self):
        while True:
            if len(self.log_message_queue) > 0:
                msg = self.log_message_queue.pop(0)
                self.display(msg)
            await asyncio.sleep(0.5)

    def add_log_message(self, msg):
        """
        Add a log message to be displayed on the device.

        :param msg: The message to be displayed.
        """
        self.log_message_queue.append(msg)

    @abc.abstractmethod
    def display(self, str):
        """
        Display a string on the device.

        :self str: The string to display.
        """
        raise NotImplementedError()

class DebugDisplay(Display):
    """
    A trivial peripheral display device implementation printing messages to the terminal.
    """
    def display(self, str):
        print("Debug Display: %s" % str)

class DisplayDeviceStream(object):
    """
    A stream class to be used for loggers logging to peripheral display devices.
    """
    def __init__(self, peripheral_display_device):
        self.peripheral_display_device = peripheral_display_device
        self.str = ""

    def write(self, str):
        self.str += str

    def flush(self):
        self.peripheral_display_device.add_log_message(self.str)
        self.str = ""

class DataLogger(Actuator):
    """
    A virtual peripheral device writing observations to internal storage.
    """

    RUNNABLE = TRUE

    def __init__(self, *args, storage_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage_path = storage_path

        self.manager.subscribe_predicate(
            lambda m: m.measurement_type == MeasurementType.REDUCED,
            self.log_measurement)

    async def run(self):
        while True:
            if len(self.log_message_queue) > 0:
                measurement = self.log_message_queue.pop(0)
                logger.info(measurement.__dict__)
                await asyncio.sleep(10)
            await asyncio.sleep(0.5)

    def log_measurement(self, measurement):
        """
        Add a log message to be displayed on the device.

        :param msg: The message to be displayed.
        """
        self.log_message_queue.append(measurement)        

class DataSerializer(Actuator):
    """
    A virtual peripheral device writing observations to internal storage.
    """
    
    def __init__(self, *args, storage_path, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage_path = storage_path

        # Subscribe to all REDUCED (processed) measurements.
        self.manager.subscribe_predicate(
            lambda m: m.measurement_type == MeasurementType.REDUCED,
            self._store_measurement)

    def _store_measurement(self, measurement):
        # Import required modules.
        import csv
        import os

        measurement_dict = measurement.__dict__

        file_name = "%s-%s.csv" % (measurement.date_time.strftime("%Y%m%d"), measurement.physical_quantity)
        path = os.path.join(self.storage_path, file_name)

        # Check whether the file exists.
        exists = os.path.isfile(path)

        # Create file and directories if it does not exist yet.
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'a', newline='') as csv_file:
            # Get the measurement object field names.
            # Sort them to ensure csv headers have
            # consistent field ordering.
            field_names = sorted(measurement_dict.keys())
            writer = csv.DictWriter(csv_file, fieldnames=field_names)

            if not exists:
                # File is new: write csv header.
                writer.writeheader()

            writer.writerow(measurement_dict)
