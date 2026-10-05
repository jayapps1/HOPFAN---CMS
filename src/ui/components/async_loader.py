"""Run database work off the Tk thread; apply only the latest live result."""
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue


class AsyncLoader:
    def __init__(self, widget):
        self.widget = widget
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hopfan-ui")
        self.queue = Queue()
        self.generations = {}
        self.closed = False
        self.timer = widget.after(50, self._poll)
        widget.bind("<Destroy>", self._destroyed, add="+")

    def submit(self, key, operation, on_success, on_error):
        if self.closed:
            return
        generation = self.generations.get(key, 0) + 1
        self.generations[key] = generation

        def run():
            try:
                result = operation()
                self.queue.put((key, generation, on_success, result))
            except Exception as exc:
                self.queue.put((key, generation, on_error, exc))

        self.executor.submit(run)

    def _poll(self):
        if self.closed:
            return
        try:
            while True:
                key, generation, callback, value = self.queue.get_nowait()
                if self.generations.get(key) == generation:
                    callback(value)
                    if self.closed:
                        return
        except Empty:
            pass
        finally:
            if not self.closed:
                self.timer = self.widget.after(50, self._poll)

    def _destroyed(self, event):
        if event.widget == self.widget:
            self.close()

    def close(self):
        if not self.closed:
            self.closed = True
            self.widget.after_cancel(self.timer)
            self.executor.shutdown(wait=False, cancel_futures=True)
