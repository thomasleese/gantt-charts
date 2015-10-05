from collections import OrderedDict, namedtuple
import colorsys
import datetime
import math

from werkzeug.utils import cached_property
import numpy as np


_Block = namedtuple('Block',
                    ['index', 'chart', 'entry', 'start', 'end', 'length'])


class InvalidGanttChart(ValueError):
    pass


class CyclicGraphError(InvalidGanttChart):
    pass


class Block(_Block):
    def as_json(self):
        return {
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
            'entry': self.entry.as_json(),
        }

    @cached_property
    def left_cells(self):
        diff = self.start - self.chart.start

        days = diff.days
        hours = diff.seconds // 60 // 60

        return days * self.chart.project.calendar.business_day_length + hours

    @cached_property
    def cells(self):
        diff = self.end - self.start

        days = diff.days
        hours = diff.seconds // 60 // 60

        if hours > self.chart.project.calendar.business_day_length:
            hours -= (24 - self.chart.project.calendar.business_day_length)

        return days * self.chart.project.calendar.business_day_length + hours

    @cached_property
    def right_cells(self):
        diff = self.chart.end - self.end

        days = diff.days
        hours = diff.seconds // 60 // 60

        return days * self.chart.project.calendar.business_day_length + hours

    @cached_property
    def fill_colour(self):
        hue = (self.index / len(self.chart.blocks))
        r, g, b = colorsys.hls_to_rgb(hue, 0.95, 0.9)
        r = int(r * 255)
        g = int(g * 255)
        b = int(b * 255)
        return 'rgb({}, {}, {})'.format(r, g, b)

    @cached_property
    def stroke_colour(self):
        hue = (self.index / len(self.chart.blocks))
        r, g, b = colorsys.hls_to_rgb(hue, 0.6, 0.5)
        r = int(r * 255)
        g = int(g * 255)
        b = int(b * 255)
        return 'rgb({}, {}, {})'.format(r, g, b)

    def applies_to(self, date, account):
        """
        Determine if a certain account is going to care about this block at a
        certain date.
        """

        return self.start.date() <= date <= self.end.date() \
            and (self.entry.has_member(account) or not self.entry.members)


class Chart:
    def __init__(self, project):
        self.project = project

        self.graph = self.topolgical_sort(project.graph)
        self.entries = [x[0] for x in self.graph]

        if not self.entries:
            raise InvalidGanttChart('No blocks.')

        existence_matrix = self.produce_existence_matrix()

        # print('-- EXISTENCE MATRIX 1 --')
        # print(existence_matrix)

        existence_matrix = self.assign_resources(existence_matrix)

        # print('-- EXISTENCE MATRIX 2 --')
        # print(existence_matrix)

        self.blocks = OrderedDict()
        for i, entry in enumerate(self.entries):
            row = existence_matrix[i, :]
            self.blocks[entry] = self.block_for_row(i, entry, row)

        self.end = max(block.end for block in self.blocks.values())

    @cached_property
    def start(self):
        try:
            return self._start
        except AttributeError:
            pass

        start_date = datetime.datetime.combine(
            self.project.calendar.start_date,
            self.project.calendar.work_starts_at)
        start_date = start_date.replace(minute=0, second=0)

        bday = self.project.calendar.business_day
        start_date = bday.rollforward(start_date)

        self._start = start_date

        return start_date

    def add_hours_to_date(self, date, duration):
        # print('Adding', duration, 'hours to', date)

        calendar = self.project.calendar
        bday = calendar.business_day
        business_hours = calendar.business_day_length

        days = duration // business_hours
        new_date = date + days * bday

        hours = (duration - days * business_hours)

        hours_left = calendar.work_ends_at.hour - new_date.hour
        if hours >= hours_left:
            new_date = new_date.replace(hour=calendar.work_starts_at.hour)
            hours -= hours_left
            new_date += bday

        new_date += datetime.timedelta(hours=int(hours))

        return new_date

    def block_for_row(self, i, entry, row):
        try:
            first_zero = row.nonzero()[0][0]
        except IndexError:
            first_zero = 0

        length = entry.normal_time_estimate

        start = self.add_hours_to_date(self.start, first_zero)
        end = self.add_hours_to_date(start, length)

        if start != end:  # for 0 duration stuff
            if end.hour == self.project.calendar.work_starts_at.hour:
                end = end.replace(hour=self.project.calendar.work_ends_at.hour)
                end -= self.project.calendar.business_day

        return Block(i, self, entry, start, end, length)

    def produce_existence_matrix(self):
        calendar = self.project.calendar
        matrix = np.zeros((len(self.entries), 0))

        for i, entry in enumerate(self.entries):
            duration = entry.normal_time_estimate

            if entry.dependencies:
                start = 0
                for dependency in entry.dependencies:
                    row_index = self.entries.index(dependency.child)
                    nonzero = matrix[row_index, :].nonzero()
                    last_nonzero = nonzero[0][-1]
                    if matrix[row_index, last_nonzero] == 1:
                        last_nonzero += 1
                    start = max(start, last_nonzero)
            else:
                start = 0

            if entry.min_start_date:
                bday = calendar.business_day

                min_start_date = entry.min_start_date
                if min_start_date.hour >= calendar.work_ends_at.hour:
                    min_start_date += bday
                    min_start_date = min_start_date.replace(
                        hour=calendar.work_starts_at.hour)
                if min_start_date.hour < calendar.work_starts_at.hour:
                    min_start_date = min_start_date.replace(
                        hour=calendar.work_starts_at.hour)

                days = -1
                while True:
                    if min_start_date >= self.start:
                        days += 1
                        min_start_date -= bday
                    else:
                        break

                hours = min_start_date.hour - calendar.work_starts_at.hour

                min_start = calendar.business_day_length * days + hours

                start = max(min_start, start)

            cols = max(start + duration, matrix.shape[1])
            if duration == 0:
                cols += 1
            matrix = Chart.upsize(matrix, cols=cols)

            if duration == 0:
                matrix[i, start] = 0.5
            else:
                for j in range(duration):
                    matrix[i, start + j] = 1

        return matrix

    def assign_resources(self, existence_matrix):
        def pick_entry_to_move(column):
            def index_key(index):
                return (self.entries[index].normal_time_estimate, index)

            indexes = column.nonzero()[0]
            index = max(indexes, key=index_key)

            return self.entries[index]

        had_a_problem = True
        while had_a_problem:
            had_a_problem = False

            for resource in self.project.resources:
                matrix = np.zeros(existence_matrix.shape)
                for i, entry in enumerate(self.entries):
                    for entry_resource in entry.resources:
                        if entry_resource.resource == resource:
                            iterator = np.nditer(existence_matrix[i, :])
                            for j, value in enumerate(iterator):
                                if value != 0:
                                    matrix[i, j] = entry_resource.amount

                for i, value in enumerate(np.nditer(matrix.sum(axis=0))):
                    if value > resource.amount:
                        existence_matrix = \
                            self.move_entry_in_existence_matrix(
                                existence_matrix,
                                pick_entry_to_move(matrix[:, i]))
                        had_a_problem = True
                        break

            for member in self.project.members:
                matrix = np.zeros(existence_matrix.shape)
                for i, entry in enumerate(self.entries):
                    for entry_member in entry.members:
                        if entry_member.member == member:
                            iterator = np.nditer(existence_matrix[i, :])
                            for j, value in enumerate(iterator):
                                if value != 0:
                                    matrix[i, j] = 1

                for i, value in enumerate(np.nditer(matrix.sum(axis=0))):
                    if value > 1:
                        existence_matrix = \
                            self.move_entry_in_existence_matrix(
                                existence_matrix,
                                pick_entry_to_move(matrix[:, i]))
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
        first_zero = matrix[row, :].nonzero()[0][0]
        last_zero = matrix[row, :].nonzero()[0][-1]

        # print('Moving', entry.name, 'by', amount)

        matrix = self.upsize(matrix, cols=max(last_zero + 2, matrix.shape[1]))

        matrix[row, first_zero] = 0
        matrix[row, last_zero + 1] = 1

        for dependency in entry.dependees:
            matrix = self.move_entry_in_existence_matrix(
                matrix, dependency.parent, amount)

        return matrix

    @cached_property
    def no_days(self):
        return math.ceil((self.end - self.start).days) + 1

    @property
    def days(self):
        for i in range(self.no_days):
            yield self.start + datetime.timedelta(days=i)

    @cached_property
    def max_entry_name(self):
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
                raise CyclicGraphError('A cyclic dependency occurred.')

        return graph_sorted

    def as_json(self):
        return {
            'blocks': [b.as_json() for b in self.blocks.values()],
            'start': self.start.isoformat(),
            'end': self.end.isoformat(),
        }
