from collections import OrderedDict, namedtuple
import datetime
import math


_Block = namedtuple('Block', ['index', 'chart', 'entry', 'start', 'end', 'length'])


class Block(_Block):
    def as_json(self):
        return {
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'entry': self.entry.as_json(),
        }

    @property
    def left_cells(self):
        diff = self.start - self.chart.start

        days = diff.days
        hours = diff.seconds // 60 // 60

        return days * self.chart.project.calendar.business_day_length + hours

    @property
    def cells(self):
        diff = self.end - self.start

        days = diff.days
        hours = diff.seconds // 60 // 60

        if hours > self.chart.project.calendar.business_day_length:
            hours -= (24 - self.chart.project.calendar.business_day_length)

        return days * self.chart.project.calendar.business_day_length + hours

    @property
    def right_cells(self):
        diff = self.chart.end - self.end

        days = diff.days
        hours = diff.seconds // 60 // 60

        return days * self.chart.project.calendar.business_day_length + hours

    @property
    def colour(self):
        return 'hsl({}, 50%, 50%)'.format((self.index / len(self.chart.blocks)) * 360)


class Chart:
    def __init__(self, project):
        self.project = project

        graph = [(task, [dep.child for dep in task.dependencies]) for task in project.entries]

        self.graph = self.topolgical_sort(graph)
        self.blocks = []

        start_times = {}
        finish_times = {}
        lengths = {}

        bday = project.calendar.business_day
        bhour = project.calendar.business_hour

        today = datetime.date.today()
        bhour_start = datetime.datetime.combine(today, bhour.start)
        bhour_end = datetime.datetime.combine(today, bhour.end)
        business_hours = int((bhour_end - bhour_start).total_seconds() / (60 * 60))

        first_start_date = project.calendar.start_date
        first_start_date = bday.rollforward(first_start_date)
        first_start_date = bhour.rollforward(first_start_date)

        for entry in self.graph:
            task = entry[0]

            if entry[1]:
                start = max(finish_times[t] for t in entry[1])
            else:
                start = first_start_date
            if start.time() == bhour.end:
                start += bhour
                start -= datetime.timedelta(hours=1)

            start_times[task] = start

            expected_time = task.normal_time_estimate
            lengths[task] = expected_time

            days = expected_time // business_hours
            hours = (expected_time - days * business_hours)

            finish = start_times[task] + days * bday + hours * bhour
            if finish.time() == bhour.start:
                finish -= bhour
                finish += datetime.timedelta(hours=1)

            finish_times[task] = finish

        if start_times and finish_times:
            self.start = min(start_times.values())
            self.end = max(finish_times.values())

            self.end = self.end.replace(hour=bhour.end.hour,
                                        minute=bhour.end.minute,
                                        second=bhour.end.second)
        else:
            self.start = None
            self.end = None

        for i, entry in enumerate(self.graph):
            task = entry[0]
            self.blocks.append(Block(i, self, task, start_times[task],
                                     finish_times[task], lengths[task]))

    @property
    def days(self):
        no_days = math.ceil((self.end - self.start).days) + 1
        for i in range(no_days):
            yield self.start + datetime.timedelta(days=i)

    def calculate_max_entry_name(self):
        return max(len(entry.name) for entry in self.project.entries)

    def topolgical_sort(self, graph_unsorted):
        graph_sorted = []

        graph_unsorted = OrderedDict(graph_unsorted)

        while graph_unsorted:
            acyclic = False
            for node, edges in list(graph_unsorted.items()):
                for edge in edges:
                    if edge in graph_unsorted:
                        break
                else:
                    acyclic = True
                    del graph_unsorted[node]
                    graph_sorted.append((node, edges))

            if not acyclic:
                raise ValueError("A cyclic dependency occurred")

        return graph_sorted

    def as_json(self):
        if not self.blocks or self.start is None or self.end is None:
            return None

        return {
            'blocks': [b.as_json() for b in self.blocks],
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
        }
