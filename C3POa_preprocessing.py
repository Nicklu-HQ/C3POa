#!/usr/bin/env python3
# Roger Volden and Chris Vollmers
# Last updated: 5 June 2018

import os
import sys
import argparse
import numpy as np

def argParser():
    '''Parses arguments.'''
    parser = argparse.ArgumentParser(description = 'Prepare sequences for\
                                                    C3POa analysis.',
                                     add_help = True,
                                     prefix_chars = '-')
    parser.add_argument('--input_fastq_file', '-i', type=str, action='store')
    parser.add_argument('--output_path', '-o', type=str, action='store')
    parser.add_argument('--quality_cutoff', '-q', type=float, action='store')
    parser.add_argument('--read_length_cutoff', '-l', type=float, action='store')
    parser.add_argument('--splint_file', '-s', type=str, action='store')
    parser.add_argument('--config', '-c', type=str, action='store', default='',
                        help='If you want to use a config file to specify paths to\
                              programs, specify them here. Use for poa, racon, water,\
                              blat, and minimap2 if they are not in your path.')
    return vars(parser.parse_args())

args = argParser()
output_path = args['output_path'] + '/'
input_file = args['input_fastq_file']
quality_cutoff = args['quality_cutoff'] # might need to type cast float, but shouldn't at this point
read_length_cutoff = args['read_length_cutoff']
splint_file = args['splint_file']

def configReader(configIn):
    '''Parses the config file.'''
    progs = {}
    for line in open(configIn):
        if line.startswith('#') or not line.rstrip().split():
            continue
        line = line.rstrip().split('\t')
        progs[line[0]] = line[1]
    # should have minimap, poa, racon, water, consensus
    # check for extra programs that shouldn't be there
    possible = set(['poa', 'minimap2', 'water', 'consensus', 'racon', 'blat'])
    inConfig = set()
    for key in progs.keys():
        inConfig.add(key)
        if key not in possible:
            raise Exception('Check config file')
    # check for missing programs
    # if missing, default to path
    for missing in possible-inConfig:
        if missing == 'consensus':
            path = 'consensus.py'
        else:
            path = missing
        progs[missing] = path
        sys.stderr.write('Using ' + str(missing)
                         + ' from your path, not the config file.\n')
    return progs

if args['config'] or args['c']:
    progs = configReader(args['config'])
    blat = progs['blat']
else:
    blat = 'blat'

def read_and_filter_fastq(input_file):
    length = 0
    for line in open(input_file):
        length += 1
    iterator = 0
    read_dict = {}
    input1 = open(input_file, 'r')
    while iterator < length:
        a = input1.readline().strip()
        b = input1.readline().strip()
        c = input1.readline().strip()
        d = input1.readline().strip()
        quals = []
        for character in d:
            number = ord(character) - 33
            quals.append(number)
        average = np.average(quals)
        name = a[1:].split()[0]
        sequence = b
        qual = d
        if len(sequence) >= read_length_cutoff and average >= quality_cutoff:
            read_dict[name] = (sequence, qual)
        iterator += 4
    return(read_dict)

def run_blat(path, reads):
    fasta_file = path + '/R2C2_temp_for_BLAT.fasta'
    input_file_fasta = open(fasta_file, 'w')

    for read in reads:
        input_file_fasta.write('>' + read + '\n' + reads[read][0] + '\n')
    input_file_fasta.close()
    os.system('%s -noHead -stepSize=1 -t=DNA q=DNA -minScore=15 \
              -minIdentity=10 %s %s %s/Splint_to_read_alignments.psl' \
              %(blat, splint_file, fasta_file, path))

def parse_blat(path):
    alignment_file = path + '/Splint_to_read_alignments.psl'
    fasta_file = path + '/R2C2_temp_for_BLAT.fasta'
    adapter_dict = {}
    length = 0
    for line in open(fasta_file):
        length += 1
    iterator = 0
    infile = open(fasta_file, 'r')
    while iterator < length:
        line = infile.readline()
        sequence = infile.readline()
        name = line[1:].strip()
        adapter_dict[name] = {}
        adapter_dict[name]['+'] = []
        adapter_dict[name]['-'] = []
        adapter_dict[name]['+'].append(('-', 1, 0))
        adapter_dict[name]['-'].append(('-', 1, len(sequence)))
        iterator += 2

    burn_dict = {}
    for line in open(alignment_file):
        a = line.strip().split('\t')
        read_name, adapter, strand = a[9], a[13], a[8]
        gaps, score = float(a[5]), float(a[0])
        sequence_length = int(a[10])
        if gaps < 50 and score > 50: # Looks for unspliced quality alignment
          if strand == '+':
                start = int(a[11]) - int(a[15])
                end = int(a[12]) + int(a[14]) - int(a[16])
          if strand == '-':
                start = int(a[11]) - int(a[14]) - int(a[16])
                end = int(a[12]) + int(a[15])
          position = min(max(0, int(start+((end-start)/2))), sequence_length-1)
          adapter_dict[read_name][strand].append((adapter, float(a[0]), position))
    return adapter_dict

def write_fastq_files(path, adapter_dict, reads):
    success = 0
    os.system('mkdir ' + path + '/splint_reads')
    for read in reads:
        name, sequence, quality = read, reads[read][0], reads[read][1]
        adapter_plus = sorted(adapter_dict[name]['+'],
                              key=lambda x: x[2], reverse=False)
        adapter_minus=sorted(adapter_dict[name]['-'],
                             key=lambda x: x[2], reverse=False)
        plus_list_name, plus_list_position = [], []
        minus_list_name, minus_list_position = [], []

        for adapter in adapter_plus:
            if adapter[0] != '-':
                plus_list_name.append(adapter[0])
                plus_list_position.append(adapter[2])
        for adapter in adapter_minus:
            if adapter[0] != '-':
                minus_list_name.append(adapter[0])
                minus_list_position.append(adapter[2])

        if 'Splint' in plus_list_name or 'Splint' in minus_list_name:
            success += 1
            try:
                out_fastq = open(path + '/splint_reads/'
                                 + str(int(success/4000))
                                 + '/R2C2_raw_reads' + '.fastq', 'a')
            except:
                os.system('mkdir ' + path + '/splint_reads/'
                          + str(int(success/4000)))
                out_fastq = open(path + '/splint_reads/'
                                 + str(int(success/4000))
                                 + '/R2C2_raw_reads' + '.fastq', 'w')
            if len(plus_list_name) > 0:
                out_fastq.write('>' + name + '_'
                                + str(plus_list_position[0]) + '\n'
                                + sequence + '\n+\n' + quality + '\n')
            else:
                out_fastq.write('>' + name + '_'
                                + str(minus_list_position[0])
                                + '\n' + sequence + '\n+\n' + quality + '\n')

def main():
    print('Reading and filtering fastq file')
    reads = read_and_filter_fastq(input_file)
    print('Running BLAT to find splint locations (This can take hours)')
    run_blat(output_path, reads)
    print('Parsing BLAT output')
    adapter_dict = parse_blat(output_path)
    print('Writing fastq output files in bins of 4000 into separate folders')
    write_fastq_files(output_path, adapter_dict, reads)

if __name__ == '__main__':
    main()
