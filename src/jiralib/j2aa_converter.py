import datetime
from urllib.parse import urlparse
from .exceptions import JiraException
import pandas as pd
from pathlib import Path


# TODO Типизировать возвращаемые JiraException
# TODO Добавить комментарии к функции
# TODO Предусмотреть возможность дублирования столбца Backlog
# TODO Порядок следования столбцов в выходном файле с учетом столбцов, состоящих из массивов


class J2aaConverter:
    """Конвертер Jira Issues в формат actionable agile для выбранной доски"""

    def __init__(self, board_config: object):
        self.board_config = board_config
        self.columns_config = {
            column["name"]: [status["id"] for status in column["statuses"]]
            for column in board_config["columnConfig"]["columns"]
        }

        self.status_to_column_map = {
            status_id: column_name
            for column_name in self.columns_config
            for status_id in self.columns_config[column_name]
        }

    @classmethod
    def from_jira_session(cls, jira_session, board_id):
        board_config = jira_session.jira.get_agile_board_configuration(board_id)
        return cls(board_config)

    @staticmethod
    # TODO Убрать передачу custom_lists отсюда и из j2aa_gui, epics + Убрать закомментированный код
    def export_to_csv(df, output_file_name, custom_lists=[]):
        """
        Сохраняет конвертированный DataFrame в csv файл

        Parameters
        ----------
        df : pandas.DataFrame
            DataFrame, подготовленный для конвертации в csv файл
        output_file_name : str
            имя выходного файла. несущестующие директории в пути будут созданы автоматически
        custom_lists : list
            список имен дополнительных столбцов, содержащих списки значений (для корректной выгрузки)
            по-умолчанию []

        Returns
        -------
        str
            абсолютный путь к экспортированному файлу

        """
        # def format_list_columns(in_df, column_names, delimeter = '|', suffix=''):
        #     out_df = pd.DataFrame()
        #     for column_name  in column_names:
        #         if column_name in in_df.columns:
        #             out_df[column_name + suffix] = "[" + in_df[column_name].str.join(delimeter) + "]"
        #     return out_df

        # LIST_FIELDS = ['labels', 'fixVersions', 'components'] + custom_lists

        # list_df = format_list_columns(df, LIST_FIELDS)

        # export_df = pd.concat([
        #     df[ [col for col in df.columns if col not in LIST_FIELDS] ],
        # list_df],
        #     axis = 1)

        export_df = df.copy()
        delimeter = "|"

        # columns = (export_df.applymap(type) == list).all()
        columns = (export_df.map(type) == list).all()

        for column_name, is_list in columns.items():
            if is_list:
                export_df[column_name] = (
                    "[" + export_df[column_name].str.join(delimeter) + "]"
                )

        Path(output_file_name).parent.resolve().mkdir(parents=True, exist_ok=True)
        export_df.to_csv(output_file_name)
        return Path(output_file_name).absolute()

    @staticmethod
    def get_status_changes(issue, add_creation=True):
        def convert_dates(s):
            return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z")

        status_changes = []
        # TODO проверить issue на наличие changelog тк возможно объект брался из REST API без параметра expand=changelog
        # TODO проверить issue на наличие поля created тк возможно объект брался из REST API без параметра fields=['created']

        for history in issue["changelog"]["histories"]:
            # TODO проверить насколько формат один и тот же. Пример 2024-01-11T21:15:11.953+0300
            created = convert_dates(history["created"])
            for item in history["items"]:
                if item["field"] == "status":
                    status_change = {
                        key: item[key]
                        for key in ["from", "fromString", "to", "toString"]
                    }
                    status_change["date"] = created
                    status_changes.append(status_change)

        if add_creation:
            # TODO проверить issue на наличие поля created тк возможно объект брался из REST API без параметра fields=['created']
            if len(status_changes) > 0:
                to = status_changes[0]["from"]
                to_string = status_changes[0]["fromString"]
            else:
                to = issue["fields"]["status"]["id"]
                to_string = issue["fields"]["status"]["name"]

            status_changes.insert(
                0,
                {
                    "date": convert_dates(issue["fields"]["created"]),
                    "from": None,
                    "fromString": None,
                    "to": to,
                    "toString": to_string,
                },
            )

        # TODO эта сортировка для перестраховки на случай если в JIRA REST API переходы не в хронологическом порядке
        status_changes.sort(key=lambda sc: sc["date"])
        return status_changes

    def convert_issues(self, issues, fields, print_log=None):
        """
        Конвертирует массив issues в DataFrame формата actionable agile.

        Список issues должен быть получен из JIRA REST API с указанием
        обязательных полей ['created', 'status']
        параметра expand='changelog'

        Parameters
        ----------
        issues : TYPE
            DESCRIPTION.
        fields : TYPE
            DESCRIPTION.
        print_log : TYPE
            DESCRIPTION.

        Raises
        ------
        JiraException
            DESCRIPTION.

        Returns
        -------
        df : TYPE
            DESCRIPTION.

        """

        print_log = print if print_log is None else print_log

        rows = []

        if len(issues) == 0:
            raise JiraException("Нет данных для конвертации")

        for issue in issues:
            try:
                board_transitions = self.__project_single_issue(issue)

                fields_dict = {}
                for field in fields:
                    # try:
                    if field == "issuetype":
                        fields_dict["issuetype"] = (
                            issue["fields"]["issuetype"]["name"]
                            if "issuetype" in issue["fields"]
                            else None
                        )
                    elif field == "labels":
                        fields_dict["labels"] = (
                            issue["fields"]["labels"]
                            if "labels" in issue["fields"]
                            else None
                        )
                    elif field == "epic":
                        fields_dict["epic_key"] = (
                            issue["fields"]["epic"]["key"]
                            if "epic" in issue["fields"]
                            else None
                        )
                        fields_dict["epic_name"] = (
                            issue["fields"]["epic"]["name"]
                            if "epic" in issue["fields"]
                            else None
                        )
                    elif field == "priority":
                        fields_dict["priority"] = (
                            issue["fields"]["priority"]["name"]
                            if "priority" in issue["fields"]
                            else None
                        )
                    elif field == "summary":
                        pass
                    # fields_dict['summary'] = issue['fields']['summary']
                    elif field == "project":
                        fields_dict["project"] = (
                            issue["fields"]["project"]["name"]
                            if "project" in issue["fields"]
                            else None
                        )
                    elif field == "assignee":
                        fields_dict["assignee"] = (
                            issue["fields"]["assignee"]["displayName"]
                            if "assignee" in issue["fields"]
                            and issue["fields"]["assignee"] is not None
                            else None
                        )
                    elif field == "reporter":
                        fields_dict["reporter"] = (
                            issue["fields"]["reporter"]["displayName"]
                            if "reporter" in issue["fields"]
                            else None
                        )
                    elif field == "creator":
                        fields_dict["creator"] = (
                            issue["fields"]["creator"]["displayName"]
                            if "creator" in issue["fields"]
                            else None
                        )
                    elif field == "projectkey":
                        fields_dict["projectkey"] = issue["key"][
                            : issue["key"].index("-")
                        ]
                    elif field == "fixVersions":
                        fields_dict["fixVersions"] = (
                            [
                                fix_version["name"]
                                for fix_version in issue["fields"]["fixVersions"]
                            ]
                            if "fixVersions" in issue["fields"]
                            else None
                        )
                    elif field == "components":
                        fields_dict["components"] = (
                            [
                                component["name"]
                                for component in issue["fields"]["components"]
                            ]
                            if "components" in issue["fields"]
                            else None
                        )
                    elif field == "status":
                        fields_dict["status"] = (
                            issue["fields"]["status"]["name"]
                            if "status" in issue["fields"]
                            else None
                        )
                    # except:
                    # print(issue)
                    # raise

                rows.append(
                    pd.Series(
                        dict(
                            list(
                                {
                                    "id": issue["key"],
                                    "link": "{uri.scheme}://{uri.netloc}/browse/{id}".format(
                                        uri=urlparse(issue["self"]), id=issue["key"]
                                    ),
                                    "name": (
                                        issue["fields"]["summary"]
                                        if "summary" in issue["fields"]
                                        else None
                                    ),
                                }.items()
                            )
                            + list(board_transitions.items())
                            + list(fields_dict.items())
                        )
                    )
                )
            except Exception as e:
                print_log(e)

        df = pd.DataFrame(rows).set_index("id")

        # check if Backlog (2nd column) contains only None values)
        if df.iloc[:, 2].isna().all():
            backlog_column_name = df.columns[2]
            df.drop(backlog_column_name, axis=1, inplace=True)

        return df

    def __project_single_issue(self, issue, print_log=None):
        print_log = print if print_log is None else print_log

        status_changes = self.get_status_changes(issue)

        # Проецируем историю смены статусов на колонки доски
        column_transitions = []
        for status_change in status_changes:
            try:
                column_name = self.status_to_column_map[status_change["to"]]
                date = status_change["date"]
                column_transitions.append({"column_name": column_name, "date": date})
            except KeyError:
                # TODO сообщить, что статус не привязан к доске
                print_log(
                    f"Статус {status_change['toString']} ({status_change['to']}) "
                    f"не привязан ни к одному статусу на доске"
                )

        # Считаем сколько времени проведено в колонках доски
        columns_cycle_time = {column_name: None for column_name in self.columns_config}
        for i in range(0, len(column_transitions)):
            current_date = column_transitions[i]["date"].date()
            next_date = (
                column_transitions[i + 1]["date"].date()
                if i < len(column_transitions) - 1
                else current_date
            )
            cycle_time = (next_date - current_date).days

            if columns_cycle_time[column_transitions[i]["column_name"]] is None:
                columns_cycle_time[column_transitions[i]["column_name"]] = cycle_time
            else:
                columns_cycle_time[column_transitions[i]["column_name"]] += cycle_time

        # Обнуляем время пребывания в статусах более поздних, чем последний. Эт она случай если были возвраты
        # TODO Проверить на наличие поля status
        status_id = issue["fields"]["status"]["id"]
        if status_id not in self.status_to_column_map:
            raise JiraException(
                f"Issue {issue['key']} Теукщий статус {status_id} находится вне доски"
            )

        current_column = self.status_to_column_map[status_id]

        column_names = [column_name for column_name in self.columns_config]
        for i in range(len(column_names) - 1, -1, -1):
            column_name = column_names[i]
            if column_name == current_column:
                break
            else:
                columns_cycle_time[column_name] = None

        # Ищем дату первого появления на доске
        first_date = None
        for column in column_transitions:
            if (
                column["column_name"] in columns_cycle_time
            ):  # columns_cycle_time.keys():
                # first_column_name = column['column_name']
                first_date = column["date"].date()
                break

        # Считаем новые даты переходов
        board_transitions = {column_name: None for column_name in self.columns_config}
        prev_date = first_date  # prev_date = None
        prev_cycle_time = 0
        for column_name, cycle_time in columns_cycle_time.items():
            if cycle_time is not None:
                current_date = prev_date + datetime.timedelta(prev_cycle_time)
                board_transitions[column_name] = current_date

                prev_date = current_date
                prev_cycle_time = cycle_time
        return board_transitions


if __name__ == "__main__":
    pass
