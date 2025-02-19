#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

_7z_path = shutil.which('7z')

if not _7z_path:
    sys.exit('7z binary could not be found!')


values = {
    'wordsize': (
        8, 12, 16, 24,
        32, 48, 64, 96,
        128, 192, 256, 273
    ),
    'dictsize': (
        '64k', '1m', '2m', '3m', '4m',
        '6m', '8m', '12m', '16m', '24m',
        '32m', '48m', '64m', '96m', '128m',
        '192m', '256m', '384m', '512m', '768m',
        '1024m', '1536m'
    ),
    'blocksize': (
        '=off', '=on', '1m', '2m', '3m',
        '4m', '6m', '8m', '12m', '16m',
        '32m', '64m', '128m', '256m', '512m',
        '1g', '2g', '4g', '8g', '16g',
        '32g', '64g'
    )
}


def directories():
    """
    Yield all directories in the current working directory. Directories that
    contain a '.' at the beginning are ignored, and the directory 'venv' is also ignored.
    Results yielded are Path objects.
    """
    for thing in Path().glob('*'):
        if thing.is_dir() and not thing.name.startswith('.'):
            if thing.name != 'venv':
                yield thing


def removeArchives():
    """
    Remove all archives/files that end with '.7z' within the current working directory.
    """
    for thing in Path().glob('*'):
        if thing.is_file() and thing.name.endswith('.7z'):
            thing.unlink()


def getTotalSizeOfArchives():
    """
    Return the sum of all '.7z' files inside the current working directory.
    """
    total_size = 0
    for archive in Path().glob('*'):
        if archive.is_file() and archive.name.endswith('.7z'):
            archive_size = archive.stat().st_size
            total_size += archive_size

    return total_size


def getLargestDirectorySize():
    """
    Return the largest directory size from 'du'
    """
    sizes = {}

    # TODO Make this all python code

    directory_sizes = subprocess.run(
        'du -sm */',  # 'm' rounds up everything to 1mb+
        capture_output=True,
        universal_newlines=True,
        shell=True  # Need a better way of doing this
    ).stdout.splitlines()

    for size in directory_sizes:
        size = size.split()

        if 'venv' in size[1]:
            continue

        sizes[size[1][:-1]] = int(size[0])

    largest = max(sizes, key=sizes.get)
    return sizes[largest]


def minimumLargestDictSize():
    """
    Return the largest dictionary size given the largest directory size
    """
    largest = getLargestDirectorySize()
    sizes = (s for s in values['dictsize'])

    # Seems like anything under 1mb will be 1 anyway (from du -sm)

    for size in sizes:
        if 'm' in size:
            size = int(size[:-1])
            if size > largest:
                return size


def minimumLargestBlockSize():
    """
    Return the largest block size given the largest directory size
    """
    largest_dirsize = getLargestDirectorySize()
    sizes = (s for s in values['blocksize'])

    for size in sizes:
        if size.endswith('m') or size.endswith('g'):
            if largest_dirsize < 1024:
                size = int(size[:-1])
                if size > largest_dirsize:
                    return size


def smallestSize(data):
    """
    Return the smallest size when testing is done.
    """
    smallest = min(data, key=data.get)
    return (smallest, data[smallest])


def runCMD(dict_size=None, word_size=None, block_size=None, threads=None):
    """
    Run 7z command for every directory, given the passed arguments.
    """
    dirs = directories()

    cmd = [
        _7z_path,
        'a',
        '-mx9',
        '--'
    ]

    if dict_size:
        dict_size = f'-md{dict_size}'
        cmd.insert(cmd.index('--'), dict_size)

    if word_size:
        word_size = f'-mfb{word_size}'
        cmd.insert(cmd.index('--'), word_size)

    if block_size:
        block_size = f'-ms{block_size}'
        cmd.insert(cmd.index('--'), block_size)

    if threads:
        threads = f'-mmt{threads}'
        cmd.insert(cmd.index('--'), threads)

    for directory in dirs:
        cmd.extend((f'{directory.name}.7z', directory.name))
        subprocess.run(cmd, stdout=subprocess.DEVNULL)
        del cmd[-2:]  # FIXME I have no idea how to do this better right now


def testAllDictSizes():
    """
    Compress all directories within the current working directory.
    This function uses 'smart' dictionary sizing to get rid of using
    larger dictionary sizes that will not affect compression or will
    give the same overall size as the minimum largest dictionary size.
    """
    info = {}

    # Using this because even larger sizes than the minimum are redundant
    largestDictSize = minimumLargestDictSize()

    for size in values['dictsize']:
        if int(size[:-1]) > largestDictSize:
            break

        print(f'Dict size: {size}')

        runCMD(size)

        info[size] = getTotalSizeOfArchives()
        removeArchives()

    return info


def testAllWordSizes(dict_size):
    info = {}

    for size in values['wordsize']:
        print(f'Word size: {size}')

        runCMD(dict_size, size)

        info[size] = getTotalSizeOfArchives()
        removeArchives()

    return info


def testAllBlockSizes(dict_size, word_size):
    info = {}

    largestBlockSize = minimumLargestBlockSize()

    for size in values['blocksize']:
        if size.endswith('m'):
            if int(size[:-1]) > largestBlockSize:
                break

        print(f'Block size: {size}')

        runCMD(dict_size, word_size, size)

        info[size] = getTotalSizeOfArchives()
        removeArchives()

    return info


def testNThreads(dict_size, word_size, block_size):
    # At least for me, the number of threads never changed the compression

    info = {}

    # Start with the max amount of threads first.
    # If the amount of threads does not change the total size,
    # return the largest for the purpose of speed.

    for i in reversed(range(1, os.cpu_count() + 1)):
        print(f'Threads: {i}')

        runCMD(dict_size, word_size, block_size, threads=i)

        info[i] = getTotalSizeOfArchives()
        removeArchives()

    return info


def main():
    removeArchives()

    dict_best = smallestSize(testAllDictSizes())
    print(f'Best dict size: {dict_best}')

    word_best = smallestSize(testAllWordSizes(dict_best[0]))
    print(f'Best word size: {word_best}')

    # TODO 1g+ block sizes

    block_best = smallestSize(testAllBlockSizes(dict_best[0], word_best[0]))
    print(f'Best block size: {block_best}')

    thread_best = smallestSize(testNThreads(
        dict_best[0], word_best[0], block_best[0])
    )

    print(f'Best thread count: {thread_best}')

    print('Testing done! Compressing with best values...')
    runCMD(dict_best[0], word_best[0], block_best[0], thread_best[0])


if __name__ == '__main__':
    main()
