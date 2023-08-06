"""Loads RQ Dashboard worker to pull jobs off the queue"""
import logging
import redis
from rq import Worker, Connection
from settings import GivSettings
listen = ['GivTCP_'+str(GivSettings.givtcp_instance)]


REDIS_URL = 'redis://127.0.0.1:6379'
conn = redis.from_url(REDIS_URL)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(listen)
        worker.work(with_scheduler=True,logging_level=logging.CRITICAL)
