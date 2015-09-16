from collections import OrderedDict, namedtuple
import datetime


_Block = namedtuple('Block', ['task', 'start', 'end'])


class Block(_Block):
    def as_json(self):
        return {
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'entry': self.task.as_json(),
        }


class Chart:
    def __init__(self, project):
        graph = [(task, [dep.child for dep in task.dependencies]) for task in project.entries]

        self.graph = self.topolgical_sort(graph)
        self.blocks = []

        start_times = {}
        finish_times = {}

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
                start_times[task] = max(finish_times[t] for t in entry[1])
            else:
                start_times[task] = first_start_date

            expected_time = task.normal_time_estimate

            days = expected_time // business_hours
            hours = (expected_time - days * business_hours)

            finish_times[task] = start_times[task] + days * bday + hours * bhour

        if start_times and finish_times:
            self.start = min(start_times.values())
            self.end = max(finish_times.values())
        else:
            self.start = None
            self.end = None

        for entry in self.graph:
            task = entry[0]
            self.blocks.append(Block(task, start_times[task],
                                     finish_times[task]))

    def topolgical_sort(self, graph_unsorted):
        graph_sorted = []

        graph_unsorted = OrderedDict(graph_unsorted)

        acyclic = False
        while graph_unsorted:
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
            return {
                'blocks': [],
                'start': None,
                'end': None,
                'range': 0
            }
        else:
            return {
                'blocks': [b.as_json() for b in self.blocks],
                'start': self.start.isoformat(),
                'end': self.end.isoformat(),
                'range': (self.end - self.start).total_seconds(),
            }
