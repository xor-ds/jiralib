import json
import datetime
from urllib.parse import urlparse

import pandas as pd


class Board:
    def __init__(self, board_config: object):
        self.board_config = board_config
        self.columns_config = {column['name']: [status['id'] for status in column['statuses']]
                               for column in board_config['columnConfig']['columns']}
        self.status_to_column_map = {status_id: column_name
                                     for column_name in self.columns_config
                                     for status_id in self.columns_config[column_name]}

    def project_issues(self, issues):
        rows = []
        for issue in issues:
            board_transitions = self.__project_single_issue(issue)
            rows.append(pd.Series(dict(list(
                {
                    'id': issue['key'],
                    'link': "{uri.scheme}://{uri.netloc}/browse/{id}".format(uri=urlparse(issue['self']), id=issue['key']),
                    'name': issue['fields']['summary'] if 'summary' in issue['fields'].keys() else issue['key']

                    # board_transitions['link'] = board_transitions.apply(lambda row: "{uri.scheme}://{uri.netloc}/browse/{id}".format(uri=urlparse(row['link']), id=row['key']),
                    #     axis=1)
                    #
                    # board_transitions.rename(columns={'key': 'id'}, inplace=True)
                    #
                    # board_transitions.set_index('id', inplace=True)

                    # 'link': issue['self'],
                    # 'name': issue['fields']['summary'] if 'summary' in issue['fields'].keys() else ''
                 }.items()) + list(board_transitions.items()))))

        return pd.DataFrame(rows).set_index('id')

    def __project_single_issue(self, issue):
        status_changes = get_status_changes(issue)

        # Проецируем историю смены статусов на колонки доски
        column_transitions = []
        for status_change in status_changes:
            try:
                column = self.status_to_column_map[status_change['to']]
                date = status_change['date']
                column_transitions.append({'column': column, 'date': date})
            except KeyError:
                # TODO сообщить, что статус не привязан к доске
                print(f"Статус {status_change['toString']} ({status_change['to']}) "
                      f"не привязан ни к одному статусу на доске")

        # Считаем сколько времени проведено в колонках доски
        columns_cycle_time = {column_name: None for column_name in self.columns_config}
        for i in range(0, len(column_transitions)):
            current_date = column_transitions[i]['date'].date()
            next_date = column_transitions[i + 1]['date'].date() if i < len(column_transitions) - 1 else current_date
            cycle_time = (next_date - current_date).days

            if columns_cycle_time[column_transitions[i]['column']] is None:
                columns_cycle_time[column_transitions[i]['column']] = cycle_time
            else:
                columns_cycle_time[column_transitions[i]['column']] += cycle_time

        # Ищем первую колонку на доске, где появилась данная issue
        first_column_name = None
        first_date = None
        for column in column_transitions:
            if column['column'] in columns_cycle_time.keys():
                first_column_name = column['column']
                first_date = column['date'].date()
                break

        # Считаем новые даты переходом
        board_transitions = {column_name: None for column_name in self.columns_config}
        last_date = None
        last_cycle_time = 0
        for column_name, cycle_time in columns_cycle_time.items():
            if cycle_time is not None:
                if last_date is None:
                    assert column_name is first_column_name
                    last_date = first_date
                board_transitions[column_name] = last_date + datetime.timedelta(last_cycle_time)
                last_cycle_time = cycle_time
                last_date = board_transitions[column_name]

        # отладка
        # print(columns_cycle_time)
        # print()
        # for t in column_transitions:
        #     print(t['date'].date(), t['column'])
        # print()
        # for sc in status_changes:
        #     print(f"{sc['date'].date()} {sc['fromString']} ({sc['from']}) --> {sc['toString']} ({sc['to']})")
        # print()

        return board_transitions


def get_status_changes(issue, add_creation=True):
    def convert_dates(s):
        return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.%f%z')

    status_changes = []
    # TODO проверить issue на наличие changelog тк возможно объект брался из REST API без параметра expand=changelog

    for history in issue['changelog']['histories']:
        # TODO проверить насколько формат один и тот же. Пример 2024-01-11T21:15:11.953+0300
        created = convert_dates(history['created'])
        for item in history['items']:
            if item['field'] == 'status':
                status_change = {key: item[key] for key in ['from', 'fromString', 'to', 'toString']}
                status_change['date'] = created
                status_changes.append(status_change)

    if add_creation:
        # TODO проверить наличие поля created
        if len(status_changes) > 0:
            to = status_changes[0]['from']
            to_string = status_changes[0]['fromString']
        else:
            to = issue['fields']['status']['id']
            to_string = issue['fields']['status']['name']

        status_changes.insert(0,
                              {'date': convert_dates(issue['fields']['created']),
                               'from': None,
                               'fromString': None,
                               'to': to,
                               'toString': to_string
                               })

    # TODO эта сортировка для перестраховки на случай если в JIRA REST API переходы не в хронологическом порядке
    status_changes.sort(key=lambda sc: sc['date'])
    return status_changes


if __name__ == '__main__':
    # issue_file = 'data/GTP-8019.json'
    issue_file = '../data/PLUS-16648.json'
    board_config_file = '../data/PLUS board-25608-configuration.json'

    # Парсим конфигурацию доски и строим карту соответствия статусов и колонок
    with open(board_config_file) as fp:
        board_config = json.load(fp)

    # Читаем поля issues и карту переходов по статусам jira workflow
    with open(issue_file) as fp:
        issue = json.load(fp)

    board = Board(board_config)
    df = board.project_issues([issue, issue, issue])
    print(df[ ['id', 'link'] ])
