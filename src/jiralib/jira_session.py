# -*- coding: utf-8 -*-

"""
Created on Tue Mar  5 17:27:18 2024

@author: Denis Sokolov
"""

from jiralib.exceptions import JiraException
from atlassian import Jira
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor


class JiraSession:
    """Клиент поддерживающий работу с jira через сессии и функции получения постраничных данных"""

    @classmethod
    def close_session(cls, url, session, verify_ssl=True):
        cls.__close_jira_session(url, session, verify_ssl)
        # cls.__close_jira_session(url, dict(name='JSESSIONID', value=session), verify_ssl)

    @staticmethod
    def __open_jira_session(url, username, password, verify_ssl=True):
        """
        Получает session id в jira

        Parameters
        ----------
        url : str
            адрес сервера jira
        username : str
            имя пользователя
        password : str
            пароль
        verify_ssl : bool, optional
            выполнять проерку ssl сертификатов. The default is True.

        Returns
        -------
        dict
            JSON ответ от сервера, содержащий session_id формате {name='JSESSIONID', 'value='session_id'}.
        """

        auth_url = "{uri.scheme}://{uri.netloc}/rest/auth/1/session".format(
            uri=urlparse(url)
        )
        auth = {"username": username, "password": password}
        resp = requests.post(auth_url, json=auth, verify=verify_ssl)

        if resp.ok:
            return resp.json()["session"]
        else:
            # resp.raise_for_status()
            raise JiraException(f"Не удалось подключиться ({resp.status_code})")

    @staticmethod
    def __close_jira_session(url, session, verify_ssl=True):
        """
        Закрывает сессию jira

        Parameters
        ----------
        url : str
            адрес jira сервера
        session : dict
            Словарь в виде {name='JSESSIONID', value='session_id'},
            где session_id - id открытой ранее сессии.
        verify_ssl : bool, optional
            выполнять проерку ssl сертификатов. The default is True.

        Returns
        -------
        bool
            True если закрытие прошло успешно, False в противоположном случае.

        """
        auth_url = "{uri.scheme}://{uri.netloc}/rest/auth/1/session".format(
            uri=urlparse(url)
        )
        cookies = {session["name"]: session["value"]}
        resp = requests.delete(auth_url, cookies=cookies, verify=verify_ssl)
        return resp.ok

    def __init__(self, url, username, password, verify_ssl=True, debug_session=False):
        """
        Создает экземпляр объекта

        Parameters
        ----------
        url : str
            адрес jira сервера.
        username : str
            имя пользователя
        password : str
            пароль
        verify_ssl : bool, optional
            True = выполнять проверку ssl сертификатов при подключении. The default is True.
        debug_session : bool, optional
            Выводить сообщения об открытии и закрытии сессии

        Returns
        -------
        None.

        """
        # self.url = url
        self.url = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))

        self.verify_ssl = verify_ssl
        self.session = self.__open_jira_session(
            self.url, username, password, verify_ssl=self.verify_ssl
        )
        self.jira = Jira(
            url=self.url,
            cookies={self.session["name"]: self.session["value"]},
            verify_ssl=self.verify_ssl,
        )
        self.debug_session = debug_session

        # TODO Убрать отладочное сообщение
        if self.debug_session:
            print(f"Сессия {self.session['value']} успешно открыта")

    # def __del__(self):
    #     if self.is_active():
    #         self.close()

    def is_active(self):
        """
        Выполняет проверку было ли выполнено подключение

        Returns
        -------
        bool
            True - если подключение установлено, False - в противоположном случае

        """
        return hasattr(self, "session")

    def close(self):
        if self.is_active():
            ret = self.__close_jira_session(
                self.url, self.session, verify_ssl=self.verify_ssl
            )
            if ret:
                # TODO убрать отладочное сообщение
                if self.debug_session:
                    print(f"Сессия {self.session['value']} успешно закрыта")
                del self.session
                del self.jira
            else:
                raise JiraException(
                    f"Попытка закрытия сессии {self.session['value']} не удалась"
                )
        else:
            raise JiraException("Попытка закрыть не активную сессию")

    def select_issues(
        self, jql, fields="*all", expand=None, chunk_size=50, callback=None
    ):
        """
        Возвращает все issues из jira по заданному фильтру, "склеивая" все страницы, возращаемые jira
        Parameters
        ----------
        jql : str
            jql запрос для отбора issues
        fields : list, optional
            список полей для включения в результат выборки. The default is "*all".
        expand : str, optional
            значение поля expand jira запросах. Если нужна история переходов, то указать 'changelog' The default is None.
        chunk_size : int, optional
            размер страницы пр иобмене с сервером jira The default is 50.
        callback : function, optional
            callback функция, вызываемая после загрузки каждой страницы The default is None.

        Returns
        -------
        issues : list
            список issues соответствующих данному запросу

        """
        if not self.is_active():
            raise JiraException(
                "Невозможно выполнить запрос. Соединение не установлено"
            )

        issues = []
        i = 0
        while True:
            chunk = self.jira.jql(
                jql, start=i, limit=chunk_size, fields=fields, expand=expand
            )
            i += len(chunk["issues"])
            issues += chunk["issues"]

            if not callback is None:
                callback(issues, len(chunk["issues"]), chunk["total"])

            if i >= chunk["total"]:
                break
        return issues

    def select_issues_parallel(
        self,
        jql,
        fields="*all",
        expand=None,
        chunk_size=50,
        callback=None,
        MAX_CONCURRENT_REQUESTS=1,
    ):
        """
        Возвращает все issues из jira по заданному фильтру, "склеивая" все страницы, возращаемые jira
        Parameters
        ----------
        jql : str
            jql запрос для отбора issues
        fields : list, optional
            список полей для включения в результат выборки. The default is "*all".
        expand : str, optional
            значение поля expand jira запросах. Если нужна история переходов, то указать 'changelog' The default is None.
        chunk_size : int, optional
            размер страницы пр иобмене с сервером jira The default is 50.
        callback : function, optional
            callback функция, вызываемая после загрузки каждой страницы The default is None.
        MAX_CONCURRENT_REQUESTS = int
            количество одновременно выполняемых запросов к jira

        Returns
        -------
        issues : list
            список issues соответствующих данному запросу

        """
        if not self.is_active():
            raise JiraException(
                "Невозможно выполнить запрос. Соединение не установлено"
            )

        i = 0
        self.issues = []
        chunk = self.jira.jql(
            jql, start=i, limit=chunk_size, fields=fields, expand=expand
        )
        self.issues += chunk["issues"]

        total = chunk["total"]

        if not callback is None:
            callback(self.issues, len(chunk["issues"]), chunk["total"])

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            steps = total // chunk_size
            workers = []
            if steps > 0:
                for j in range(steps):
                    start = (j + 1) * chunk_size
                    worker = executor.submit(
                        self._select_issues,
                        jql,
                        start=start,
                        chunk_size=chunk_size,
                        fields=fields,
                        expand=expand,
                        callback=callback,
                    )
                    workers.append(worker)

                for worker in workers:
                    worker.result()

        return self.issues

    def _select_issues(
        self, jql, start=0, chunk_size=50, fields="*all", expand=None, callback=None
    ):
        chunk = self.jira.jql(
            jql, start=start, limit=chunk_size, fields=fields, expand=expand
        )

        self.issues += chunk["issues"]
        if not callback is None:
            callback(self.issues, len(chunk["issues"]), chunk["total"])

    def select_issues_for_board(
        self,
        board_id,
        jql=None,
        fields="*all",
        expand=None,
        chunk_size=50,
        callback=None,
        MAX_CONCURRENT_REQUESTS=1,
    ):
        """
        Возвращает все issues из jira для доски, "склеивая" все страницы, возращаемые jira

        Parameters
        ----------
        board_id : int, str
            id доски из которой буду браться по-умолчанию issues.
        jql : str
            jql запрос для отбора issues.
        fields : list, optional
            список полей для включения в результат выборки. The default is "*all".
        expand : str, optional
            значение поля expand jira запросах. Если нужна история переходов, то указать 'changelog' The default is None.
        chunk_size : int, optional
            размер страницы пр иобмене с сервером jira The default is 50.
        callback : function, optional
            callback функция, вызываемая после загрузки каждой страницы The default is None.

        Returns
        -------
        issues : list
            список issues соответствующих данному запросу

        """

        if not self.is_active():
            raise JiraException(
                "Невозможно выполнить запрос. Соединение не установлено"
            )

        print(f" MAX_CONCURRENT_REQUESTS = {MAX_CONCURRENT_REQUESTS}")

        self.issues = []
        i = 0
        chunk = self.jira.get_issues_for_board(
            board_id, jql, start=i, limit=chunk_size, fields=fields, expand=expand
        )

        i += len(chunk["issues"])
        self.issues += chunk["issues"]
        total = chunk["total"]

        if not callback is None:
            callback(self.issues, len(chunk["issues"]), chunk["total"])

        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
            steps = total // chunk_size
            workers = []
            if steps > 0:
                for j in range(steps):
                    start = (j + 1) * chunk_size
                    worker = executor.submit(
                        self._get_chunk_issues_for_board,
                        board_id,
                        jql,
                        start=start,
                        chunk_size=chunk_size,
                        fields=fields,
                        expand=expand,
                        callback=callback,
                    )
                    workers.append(worker)

                for worker in workers:
                    worker.result()

        return self.issues

    def _get_chunk_issues_for_board(
        self,
        board_id,
        jql,
        start=0,
        chunk_size=50,
        fields="*all",
        expand=None,
        callback=None,
    ):
        try:
            chunk = self.jira.get_issues_for_board(
                board_id,
                jql,
                start=start,
                limit=chunk_size,
                fields=fields,
                expand=expand,
            )
        except Exception as e:
            print(e)
            return self._get_chunk_issues_for_board(
                board_id,
                jql,
                start=start,
                chunk_size=chunk_size,
                fields=fields,
                expand=expand,
                callback=callback,
            )

        self.issues += chunk["issues"]
        if not callback is None:
            callback(self.issues, len(chunk["issues"]), chunk["total"])


if __name__ == "__main__":
    import urllib3

    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    urllib3.disable_warnings()
    pass
