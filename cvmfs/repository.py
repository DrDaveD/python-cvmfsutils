#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created by René Meusel
This file is part of the CernVM File System auxiliary tools.
"""

import abc
import os
import tempfile
import requests
import collections
from datetime import datetime
import dateutil.parser
from dateutil.tz import tzutc
import shutil
import zlib

import _common
import cvmfs
from manifest import Manifest
from catalog import Catalog
from history import History
from whitelist import Whitelist
from certificate import Certificate
from _exceptions import *


class RepositoryIterator(object):
    """ Iterates through all directory entries in a whole Repository """

    class _CatalogIterator:
        def __init__(self, catalog):
            self.catalog          = catalog
            self.catalog_iterator = catalog.__iter__()


    def __init__(self, repository, catalog_hash=None):
        self.repository    = repository
        self.catalog_stack = collections.deque()
        if catalog_hash is None:
            catalog = repository.retrieve_root_catalog()
        else:
            catalog = repository.retrieve_catalog(catalog_hash)
        self._push_catalog(catalog)


    def __iter__(self):
        return self


    def next(self):
        full_path, dirent = self._get_next_dirent()
        if dirent.is_nested_catalog_mountpoint():
            self._fetch_and_push_catalog(full_path)
            return self.next() # same directory entry is also in nested catalog
        return full_path, dirent


    def _get_next_dirent(self):
        try:
            return self._get_current_catalog().catalog_iterator.next()
        except StopIteration, e:
            self._pop_catalog()
            if not self._has_more():
                raise StopIteration()
            return self._get_next_dirent()


    def _fetch_and_push_catalog(self, catalog_mountpoint):
        current_catalog = self._get_current_catalog().catalog
        nested_ref      = current_catalog.find_nested_for_path(catalog_mountpoint)
        if not nested_ref:
            raise NestedCatalogNotFound(self.repository)
        new_catalog     = nested_ref.retrieve_from(self.repository)
        self._push_catalog(new_catalog)


    def _has_more(self):
        return len(self.catalog_stack) > 0


    def _push_catalog(self, catalog):
        catalog_iterator = self._CatalogIterator(catalog)
        self.catalog_stack.append(catalog_iterator)

    def _get_current_catalog(self):
        return self.catalog_stack[-1]

    def _pop_catalog(self):
        return self.catalog_stack.pop()


class CatalogTreeIterator(object):
    class _CatalogWrapper:
        def __init__(self, repository):
            self.repository        = repository
            self.catalog           = None
            self.catalog_reference = None

        def get_catalog(self):
            if self.catalog is None:
                self.catalog = self.catalog_reference.retrieve_from(self.repository)
            return self.catalog

    def __init__(self, repository, root_catalog):
        if not root_catalog:
            root_catalog = repository.retrieve_root_catalog()
        self.repository    = repository
        self.catalog_stack = collections.deque()
        wrapper            = self._CatalogWrapper(self.repository)
        wrapper.catalog    = root_catalog
        self._push_catalog_wrapper(wrapper)

    def __iter__(self):
        return self

    def next(self):
        if not self._has_more():
            raise StopIteration()
        catalog = self._pop_catalog()
        self._push_nested_catalogs(catalog)
        return catalog

    def _has_more(self):
        return len(self.catalog_stack) > 0

    def _push_nested_catalogs(self, catalog):
        for nested_reference in catalog.list_nested():
            wrapper = self._CatalogWrapper(self.repository)
            wrapper.catalog_reference = nested_reference
            self._push_catalog_wrapper(wrapper)

    def _push_catalog_wrapper(self, catalog):
        self.catalog_stack.append(catalog)

    def _pop_catalog(self):
        wrapper = self.catalog_stack.pop()
        return wrapper.get_catalog()


class Cache(object):
    """ Abstract base class for a caching strategy """

    """ Try to get an object from the cache
        :file_name  name of the object to be retrieved
        :return     a file object of the cached object or None if not found
    """
    @abc.abstractmethod
    def get(self, file_name):
        pass

    """ Open a transaction to accomodate a new object in the cache
        :file_name  name of the object to be stored in the cache
        :return     a writable file object to a temporary storage location
    """
    @abc.abstractmethod
    def transaction(self, file_name):
        pass

    """ Commit a filled file object obtained via transaction() into the cache
        :resource   a file object obtained by transaction() and filled with data
        :return     a file object to the committed object
    """
    @abc.abstractmethod
    def commit(self, resource):
        pass


class DummyCache(Cache):
    """ A dummy cache uses temporary storage without actual cache logic """

    def get(self, file_name):
        return None

    def transaction(self, file_name):
        return tempfile.NamedTemporaryFile("w+b")

    def commit(self, resource):
        resource.seek(0)
        return resource


class DiskCache(Cache):
    """ Maintains a fully functional and reusable disk cache """

    class TransactionFile(file):
        """ Wrapper around a writable file. The actual file will be renamed
        to a different location once it is closed
        """

        def __init__(self, name, tmp_dir):
            self.__final_destination_path = name
            temp_path = tempfile.mktemp(dir=tmp_dir, prefix='tmp.')
            super(DiskCache.TransactionFile, self).__init__(temp_path, 'w+b')

        def __del__(self):
            if not self.closed:
                self.close()

        def commit(self):
            super(DiskCache.TransactionFile, self).close()
            os.rename(self.name, self.__final_destination_path)
            return open(self.__final_destination_path, "rb")

    def __init__(self, cache_dir):
        if not os.path.exists(cache_dir):
            cache_dir = tempfile.mkdtemp(dir='/tmp', prefix='cache.')
        self._cache_dir = cache_dir
        self._create_cache_structure()
        self._cleanup_metadata()

    def _cleanup_metadata(self):
        metadata_file_list = [
            os.path.join(self._cache_dir, _common._MANIFEST_NAME),
            os.path.join(self._cache_dir, _common._LAST_REPLICATION_NAME),
            os.path.join(self._cache_dir, _common._REPLICATING_NAME),
            os.path.join(self._cache_dir, _common._WHITELIST_NAME)
        ]
        for metadata_file in metadata_file_list:
            try:
                os.remove(metadata_file)
            except OSError:
                pass

    def _create_dir(self, path):
        cache_full_path = os.path.join(self._cache_dir, path)
        if not os.path.exists(cache_full_path):
            os.mkdir(cache_full_path, 0755)

    def _create_cache_structure(self):
        self._create_dir('data')
        for i in range(0x00, 0xff + 1):
            new_folder = '{0:#0{1}x}'.format(i, 4)[2:]
            self._create_dir(os.path.join('data', new_folder))
        self._create_dir(os.path.join('data', 'txn'))

    def get_transaction_dir(self):
        return os.path.join(self._cache_dir, 'data', 'txn')

    def get_cache_path(self):
        return str(self._cache_dir)

    def transaction(self, file_name):
        full_path = os.path.join(self._cache_dir, file_name)
        tmp_dir = self.get_transaction_dir()
        return DiskCache.TransactionFile(full_path, tmp_dir)

    def commit(self, resource):
        return resource.commit()

    def get(self, file_name):
        full_path = os.path.join(self._cache_dir, file_name)
        if os.path.exists(full_path):
            try:
                # if the file has been removed by now the open method
                # throws an exception
                return open(full_path, 'rb')
            except IOError, e:
                raise FileNotFoundInRepository(full_path)
        return None


class Fetcher(object):
    """ Abstract wrapper around a Fetcher """

    __metadata__ = abc.ABCMeta

    def __init__(self, source, cache_dir = None):
        self.__cache = DiskCache(cache_dir) if cache_dir else DummyCache()
        self.source = source

    def _make_file_uri(self, file_name):
        return os.path.join(self.source, file_name)

    def get_cache_path(self):
        if self.__cache:
            return self.__cache.get_cache_path()

    def retrieve_file(self, file_name):
        """
        Method to retrieve a file from the cache if exists, or from
        the repository if it doesn't. In case it has to be retrieved from
        the repository it will also be decompressed before being stored in
        the cache
        :param file_name: name of the file in the repository
        :return: a file read-only file object that represents the cached file
        """
        return self._retrieve(file_name, self._retrieve_file)

    def retrieve_raw_file(self, file_name):
        """
        Method to retrieve a file from the cache if exists, or from
        the repository if it doesn't. In case it has to be retrieved from
        the repository it won't be decompressed
        :param file_name: name of the file in the repository
        :return: a file read-only file object that represents the cached file
        """
        return self._retrieve(file_name, self._retrieve_raw_file)

    def _retrieve(self, file_name, retrieve_fn):
        cached_file_ro = self.__cache.get(file_name)
        if cached_file_ro:
            return cached_file_ro

        cached_file_rw = self.__cache.transaction(file_name)
        retrieve_fn(file_name, cached_file_rw)
        return self.__cache.commit(cached_file_rw)


    @abc.abstractmethod
    def _retrieve_file(self, file_name, cached_file):
        """ Abstract method to retrieve a file from the repository """
        pass

    @abc.abstractmethod
    def _retrieve_raw_file(self, file_name, cached_file):
        """ Abstract method to retrieve a raw file from the repository """
        pass


class LocalFetcher(Fetcher):
    """ Retrieves files only from the local cache """

    def __init__(self, local_repo, cache_dir = None):
        super(LocalFetcher, self).__init__(local_repo, cache_dir)

    def _retrieve_file(self, file_name, cached_file):
        full_path = self._make_file_uri(file_name)
        if os.path.exists(full_path):
            compressed_file = open(full_path, 'r')
            decompressed_content = zlib.decompress(compressed_file.read())
            compressed_file.close()
            cached_file.write(decompressed_content)
        else:
            raise FileNotFoundInRepository(file_name)

    def _retrieve_raw_file(self, file_name, cached_file):
        """ Retrieves the file directly from the source """
        full_path = self._make_file_uri(file_name)
        if os.path.exists(full_path):
            raw_file = open(full_path, 'rb')
            cached_file.write(raw_file.read())
            raw_file.close()
        else:
            raise FileNotFoundInRepository(file_name)


class RemoteFetcher(Fetcher):
    """ Retrieves files from the local cache if found, and from
    remote otherwise
    """

    def __init__(self, repo_url, cache_dir = None):
        super(RemoteFetcher, self).__init__(repo_url, cache_dir)
        self._user_agent      = cvmfs.__package_name__ + "/" + cvmfs.__version__
        self._default_headers = { 'User-Agent': self._user_agent }

    def _download_content_and_store(self, cached_file, file_url):
        response = requests.get(file_url, stream=True,
                                          headers=self._default_headers)
        if response.status_code != requests.codes.ok:
            raise FileNotFoundInRepository(file_url)
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                cached_file.write(chunk)

    def _download_content_and_decompress(self, cached_file, file_url):
        response = requests.get(file_url, stream=False,
                                          headers=self._default_headers)
        if response.status_code != requests.codes.ok:
            raise FileNotFoundInRepository(file_url)
        decompressed_content = zlib.decompress(response.content)
        cached_file.write(decompressed_content)

    def _retrieve_file(self, file_name, cached_file):
        file_url = self._make_file_uri(file_name)
        self._download_content_and_decompress(cached_file, file_url)

    def _retrieve_raw_file(self, file_name, cached_file):
        file_url = self._make_file_uri(file_name)
        self._download_content_and_store(cached_file, file_url)


class Repository(object):
    """ Wrapper around a CVMFS Repository representation """

    def __init__(self, source, cache_dir = None):
        if source == '':
            raise Exception('source cannot be empty')
        self._fetcher = self.__init_fetcher(source, cache_dir)
        self._endpoint = source
        self._opened_catalogs = {}
        self._read_manifest()
        self._try_to_get_last_replication_timestamp()
        self._try_to_get_replication_state()


    @staticmethod
    def __init_fetcher(source, cache_dir):
        if source.startswith("http://"):
            return RemoteFetcher(source, cache_dir)
        if os.path.exists(source):
            return LocalFetcher(source, cache_dir)
        if os.path.exists(os.path.join('/srv/cvmfs', source)):
            return LocalFetcher(os.path.join('/srv/cvmfs', source, cache_dir))
        else:
            raise RepositoryNotFound(source)


    def __iter__(self):
        return RepositoryIterator(self)


    def _read_manifest(self):
        try:
            with self._fetcher.retrieve_raw_file(_common._MANIFEST_NAME) as manifest_file:
                self.manifest = Manifest(manifest_file)
            self.fqrn = self.manifest.repository_name
        except FileNotFoundInRepository, e:
            raise RepositoryNotFound(self._endpoint)


    @staticmethod
    def __read_timestamp(timestamp_string):
        local_ts = dateutil.parser.parse(timestamp_string,
                                         ignoretz=False,
                                         tzinfos=_common.TzInfos.get_tzinfos())
        return local_ts.astimezone(tzutc())


    def _try_to_get_last_replication_timestamp(self):
        try:
            with self._fetcher.retrieve_raw_file(_common._LAST_REPLICATION_NAME) as rf:
                timestamp = rf.readline()
                self.last_replication = self.__read_timestamp(timestamp)
            if not self.has_repository_type():
                self.type = 'stratum1'
        except FileNotFoundInRepository, e:
            self.last_replication = datetime.fromtimestamp(0, tz=tzutc())


    def _try_to_get_replication_state(self):
        self.replicating = False
        try:
            with self._fetcher.retrieve_raw_file(_common._REPLICATING_NAME) as rf:
                timestamp = rf.readline()
                self.replicating = True
                self.replicating_since = self.__read_timestamp(timestamp)
        except FileNotFoundInRepository, e:
            pass


    def verify(self, public_key_path):
        """ Use a public key to verify the repository's authenticity """
        whitelist   = self.retrieve_whitelist()
        certificate = self.retrieve_certificate()
        if not whitelist.verify_signature(public_key_path):
            raise RepositoryVerificationFailed("Public key doesn't fit", self)
        if whitelist.expired():
            raise RepositoryVerificationFailed("Whitelist expired", self)
        if not whitelist.contains(certificate):
            raise RepositoryVerificationFailed("Certificate not in whitelist", self)
        if not self.manifest.verify_signature(certificate):
            raise RepositoryVerificationFailed("Certificate doesn't fit", self)
        return True


    def catalogs(self, root_catalog = None):
        return CatalogTreeIterator(self, root_catalog)


    def has_repository_type(self):
        return hasattr(self, 'type') and self.type != 'unknown'


    def has_history(self):
        return self.manifest.has_history()


    def retrieve_history(self):
        if not self.has_history():
            raise HistoryNotFound(self)
        history_db = self.retrieve_object(self.manifest.history_database, 'H')
        return History(history_db)


    def retrieve_whitelist(self):
        """ retrieve and parse the .cvmfswhitelist file from the repository """
        whitelist = self._fetcher.retrieve_raw_file(_common._WHITELIST_NAME)
        return Whitelist(whitelist)


    def retrieve_certificate(self):
        """ retrieve the repository's certificate file """
        certificate = self.retrieve_object(self.manifest.certificate, 'X')
        return Certificate(certificate)


    def retrieve_object(self, object_hash, hash_suffix = ''):
        """ Retrieves an object from the content addressable storage """
        path = "data/" + object_hash[:2] + "/" + object_hash[2:] + hash_suffix
        return self._fetcher.retrieve_file(path)


    def retrieve_root_catalog(self):
        return self.retrieve_catalog(self.manifest.root_catalog)


    def retrieve_catalog_for_path(self, needle_path):
        """ Recursively walk down the Catalogs and find the best fit for a path """
        clg = self.retrieve_root_catalog()
        while True:
            new_nested_reference = clg.find_nested_for_path(needle_path)
            if new_nested_reference is None:
                break
            nested_reference = new_nested_reference
            clg = self.retrieve_catalog(nested_reference.hash)
        return clg


    def close_catalog(self, catalog):
        try:
            del self._opened_catalogs[catalog.hash]
        except KeyError, e:
            print "not found:" , catalog.hash
            pass


    def retrieve_catalog(self, catalog_hash):
        """ Download and open a catalog from the repository """
        if catalog_hash in self._opened_catalogs:
            return self._opened_catalogs[catalog_hash]
        return self._retrieve_and_open_catalog(catalog_hash)

    def _retrieve_and_open_catalog(self, catalog_hash):
        catalog_file = self.retrieve_object(catalog_hash, 'C')
        new_catalog = Catalog(catalog_file, catalog_hash)
        self._opened_catalogs[catalog_hash] = new_catalog
        return new_catalog


def all_local():
    d = _common._REPO_CONFIG_PATH
    if not os.path.isdir(d):
        raise _common.CvmfsNotInstalled
    return [ Repository(repo) for repo in os.listdir(d) if os.path.isdir(os.path.join(d, repo)) ]

def all_local_stratum0():
    return [ repo for repo in all_local() if repo.type == 'stratum0' ]

def open_repository(repository_path, **kwargs):
    """ wrapper function accessing a repository by URL, local FQRN or path """
    cache_dir  = kwargs['cache_dir']  if 'cache_dir'  in kwargs.keys() else None
    public_key = kwargs['public_key'] if 'public_key' in kwargs.keys() else None
    repo = Repository(repository_path, cache_dir)
    if public_key:
        repo.verify(public_key)
    return repo
