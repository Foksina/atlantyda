import random


class ValueGenerator:
    """Kolejne wartości pomiaru. Pierwsza jest wartością początkową."""

    def __init__(self, start, minimum=None, maximum=None, step=0.5, rng=None):
        if step < 0:
            raise ValueError("Krok zmiany wartości nie może być ujemny.")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError("Wartość minimalna nie może być większa od maksymalnej.")
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.rng = rng or random.Random()
        self.current = self._clamp(start)
        self._started = False

    def _clamp(self, value):
        if self.minimum is not None and value < self.minimum:
            return self.minimum
        if self.maximum is not None and value > self.maximum:
            return self.maximum
        return value

    def next_value(self):
        if not self._started:
            self._started = True
            return self.current
        if self.step == 0:
            return self.current
        self.current = self._clamp(self.current + self.rng.uniform(-self.step, self.step))
        return self.current
