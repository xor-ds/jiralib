# -*- coding: utf-8 -*-

"""
Created on Sat Mar  9 14:05:52 2024


@author: Sokolov-DeV
"""

import urllib3.exceptions


class JiraException(Exception):
    pass


class JiraHttpError(JiraException):
    def __init__(self, code, msg=None):
        super().__init__(
            f"HTTP connection error: {code}" + (f" ({msg})" if msg else "")
        )
        self.code = code


class JiraInactiveConnection(JiraException):
    pass


if __name__ == "__main__":
    import jira_session

    try:
        # js = jira_session.JiraSession('http://jira.sberbank1.ru', 'Sokolov-DeV', 'Sendstring-48')
        js = jira_session.JiraSession("http://jira.sberbank.ru", "", "")
    except urllib3.exceptions.NameResolutionError as e:
        print(e)
    except (
        urllib3.exceptions.ConnectionError,
        urllib3.exceptions.NameResolutionError,
    ) as e:
        print(e)
    except Exception as e:
        print(e)

    # InvalidSchema если не верный протокол
    # requests.exceptions.ConnectTimeout если указан протокол http
    # "Failed to resolve" in str(e) если ошибка в адресе

    try:
        raise JiraHttpError(400, "reason")
        # raise JiraException()
    except JiraHttpError as e:
        print(e)
    except JiraException as e:
        print(e)
