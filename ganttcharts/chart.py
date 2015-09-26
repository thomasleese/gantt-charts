from collections import OrderedDict, namedtuple
import datetime
import math

import numpy as np


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

        self.graph = self.topolgical_sort(project.graph)
        self.entries = [x[0] for x in self.graph]

        existence_matrix = self.produce_existence_matrix()

        print('-- EXISTENCE MATRIX 1 --')
        print(existence_matrix)

        existence_matrix = self.assign_resources(existence_matrix)

        print('-- EXISTENCE MATRIX 2 --')
        print(existence_matrix)

        self.blocks = OrderedDict()
        for i, entry in enumerate(self.entries):
            row = existence_matrix[i,:]
            self.blocks[entry] = self.block_for_row(i, entry, row)

        if self.blocks:
            self.end = max(block.end for block in self.blocks.values())
        else:
            self.end = None

    @property
    def start(self):
        try:
            return self._start
        except AttributeError:
            pass

        start_date = datetime.datetime.combine(self.project.calendar.start_date, self.project.calendar.work_starts_at)
        start_date = start_date.replace(minute=0, second=0)

        bday = self.project.calendar.business_day
        start_date = bday.rollforward(start_date)

        self._start = start_date

        return start_date

    def add_hours_to_date(self, date, duration):
        print('Adding', duration, 'hours to', date)

        bday = self.project.calendar.business_day
        business_hours = self.project.calendar.business_day_length

        days = duration // business_hours
        new_date = date + days * bday

        hours = (duration - days * business_hours)

        hours_left = self.project.calendar.work_ends_at.hour - new_date.hour
        if hours >= hours_left:
            new_date = new_date.replace(hour=self.project.calendar.work_starts_at.hour)
            hours -= hours_left
            new_date += bday

        new_date += datetime.timedelta(hours=int(hours))

        return new_date

    def block_for_row(self, i, entry, row):
        first_zero = row.nonzero()[0][0]
        last_zero = row.nonzero()[0][-1]

        length = last_zero - first_zero + 1

        start = self.add_hours_to_date(self.start, first_zero)
        end = self.add_hours_to_date(start, length)

        return Block(i, self, entry, start, end, length)

    def produce_existence_matrix(self):
        matrix = np.zeros((len(self.entries), 0))

        for i, entry in enumerate(self.entries):
            duration = entry.normal_time_estimate

            if entry.dependencies:
                start = 0
                for dependency in entry.dependencies:
                    row = self.entries.index(dependency.child)
                    for value in np.nditer(matrix[row,:]):
                        if value == 0:
                            break
                        start += 1
            else:
                start = 0

            matrix = Chart.upsize(matrix, cols=max(start + duration, matrix.shape[1]))

            for j in range(duration):
                matrix[i, start + j] = 1

        return matrix

    def assign_resources(self, existence_matrix):
        had_a_problem = True
        while had_a_problem:
            had_a_problem = False

            for resource in self.project.resources:
                matrix = np.zeros(existence_matrix.shape)
                for i, entry in enumerate(self.entries):
                    for entry_resource in entry.resources:
                        if entry_resource.resource == resource:
                            for j, value in enumerate(np.nditer(existence_matrix[i,:])):
                                if value != 0:
                                    matrix[i,j] = entry_resource.amount

                print('-- STAGE #2 SUMS - {} --'.format(resource.name))
                print(matrix.sum(axis=0))

                for i, value in enumerate(np.nditer(matrix.sum(axis=0))):
                    if value > resource.amount:
                        print('WE HAVE A PROBLEM AT', i)
                        entry_index = matrix[:, i].nonzero()[0][0]
                        existence_matrix = self.move_entry_in_existence_matrix(existence_matrix, self.entries[entry_index])
                        had_a_problem = True
                        break

        return existence_matrix

    @staticmethod
    def upsize(matrix, rows=None, cols=None):
        old_shape = matrix.shape
        new_shape = (rows or old_shape[0], cols or old_shape[1])
        if old_shape == new_shape:
            return matrix
        else:
            new_matrix = np.zeros(new_shape)
            new_matrix[:old_shape[0], :old_shape[1]] = matrix
            return new_matrix

    def move_entry_in_existence_matrix(self, matrix, entry, amount=1):
        row = self.entries.index(entry)
        first_zero = matrix[row,:].nonzero()[0][0]
        last_zero = matrix[row,:].nonzero()[0][-1]

        print('Moving', entry.name, 'by', amount)

        matrix = self.upsize(matrix, cols=max(last_zero + 2, matrix.shape[1]))

        matrix[row,first_zero] = 0
        matrix[row,last_zero + 1] = 1

        for dependency in entry.dependees:
            matrix = self.move_entry_in_existence_matrix(matrix, dependency.parent, amount)

        return matrix

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
