from product_integrity import pinned, state_path
import io
import struct
import time
HEADER = struct.Struct('<IHH4B')
MAX_FRAME = 1048576
CHUNK = 32768

class WireError(RuntimeError):
    pass

class SenserWire:

    def __init__(self, driver, budget=180):
        self.driver, self.budget = (driver, budget)
        self.sequence, self.healthy = (1, True)

    def _timeout(self):
        left = self.deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError('USB transaction deadline exceeded')
        return max(1, min(5000, int(left * 1000)))

    def _read(self, size):
        data = self.driver.read(size, timeout=self._timeout())
        if len(data) > size:
            raise WireError('USB read exceeds requested length')
        return bytes(data)

    def _exact(self, size):
        data = bytearray()
        while len(data) < size:
            part = self._read(size - len(data))
            if not part:
                raise WireError('Empty read before end of response')
            data.extend(part)
        return bytes(data)

    def send(self, pfunc, payload, *, maximum, progress=None):
        if not self.healthy:
            raise WireError('USB outcome unknown; refusing further commands')
        if not payload or len(payload) > 65536 or (not 0 < maximum <= 512 * 1024 * 1024 + 4):
            raise ValueError('Invalid bounded transaction size')
        self.deadline = time.monotonic() + self.budget
        out = io.BytesIO()
        try:
            self.driver.timeout = self._timeout()
            sent = self.driver.write(HEADER.pack(len(payload), pfunc, self.sequence, 0, 0, 0, 0) + payload)
            if sent != HEADER.size + len(payload):
                raise WireError('Short command write; outcome unknown')
            remaining, total, response = (None, None, None)
            while True:
                size, function, seq, version, micon, offset, status = HEADER.unpack(self._exact(HEADER.size))
                if (function, seq, micon, offset) != (pfunc, self.sequence, 0, 0):
                    raise WireError('Unexpected response header identity')
                if version not in (0, 3):
                    raise WireError('Unexpected response version')
                if total is None:
                    if not 0 < size <= maximum:
                        raise WireError('Response length outside bounds')
                    remaining = total = size
                    response = status
                if size != remaining or status != response:
                    raise WireError('Continuation length or response changed')
                count = min(size, MAX_FRAME)
                done = 0
                while done < count:
                    block_size = min(count - done, CHUNK)
                    out.write(self._exact(block_size))
                    done += block_size
                    if block_size % 512 == 0:
                        if self._read(512):
                            raise WireError('Expected USB zero-length packet')
                    if progress:
                        progress(out.tell(), total)
                remaining -= count
                if not remaining:
                    break
            self.sequence = self.sequence + 1 & 65535
            return (response, out.getvalue())
        except BaseException:
            self.healthy = False
            raise
