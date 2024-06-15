import logging
import os
from subprocess import Popen, PIPE

import yaml
import click


logging.basicConfig(level=logging.DEBUG)


def read_yaml(path: str):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def config_ethernet(interface, addr, netmask, gateway):
    if addr and netmask:
        os.system(f'ifconfig {interface} {addr} netmask {netmask} up')
    if gateway:
        os.system(f'route add default gw {gateway} {interface}')


def mount_block_device(blkdev_path: str, mountpoint: str, ro: bool = True) -> bool:
    cmd = ['mount', '-t', 'auto', '-o', 'ro' if ro else 'rw', blkdev_path, mountpoint]
    p = Popen(cmd, stdout=PIPE)
    p.communicate()
    return p.returncode == 0


def unmount_block_device(mountpoint: str) -> bool:
    cmd = ['umount', '-l', mountpoint]
    p = Popen(cmd, stdout=PIPE)
    p.communicate()
    return p.returncode == 0


def remount_block_device(blkdev_path: str, mountpoint: str, ro: bool = True):
    unmount_block_device(mountpoint)
    mount_block_device(blkdev_path, mountpoint, ro)


@click.command()
@click.option('--blkdev-path', type=click.Path(exists=True), required=True)
@click.option('--mount-path', type=click.Path(exists=True), required=True)
@click.option('--config-path', type=click.Path(exists=True), default='config.yaml')
def main(
        blkdev_path: str,
        mount_path: str,
        config_path: str
):
    remounted_device = False

    objs = read_yaml(config_path)

    # Configure network
    net_config = objs.get('network')
    if net_config:
        interface = net_config.get('interface')
        address = net_config.get('address')
        netmask = net_config.get('netmask')
        gateway = net_config.get('gateway')
        if interface:
            logging.info(f'configure network - {interface}')
            logging.info(f'address: {address}, netmask: {netmask}, gateway: {gateway}')
            config_ethernet(interface, address, netmask, gateway)

    # Run applications
    applications = objs.get('applications', [])
    for item in applications:
        name = item.get('name', '<unnamed>')
        enabled = item.get('enabled', False)
        read_only = item.get('ro', True)
        path = item['path']
        command = item['command']

        if not enabled:
            continue

        if not read_only and not remounted_device:
            logging.info(f'remount block device. because application requires rw')
            remount_block_device(blkdev_path, path, ro=False)
            remounted_device = True

        logging.info(f'run application - {name}')
        command = command.replace('{:blkdev-path:}', blkdev_path)
        command = command.replace('{:mount-path:}', mount_path)
        prev_wd = os.getcwd()
        os.chdir(os.path.join(prev_wd, path))
        os.system(command)
        os.chdir(prev_wd)


if __name__ == '__main__':
    main()
