#!/usr/bin/python
# -*- coding: UTF-8 -*-
import sys, getopt

def main(argv):
   inputfile = ''
   outputfile = ''
   try:
      opts, args = getopt.getopt(argv,"hi:o:",["ifile=","ofile="])
   except getopt.GetoptError:
      print 'test.py -i <inputfile> -o <outputfile>'
      sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
         print 'test.py -i <inputfile> -o <outputfile>'
         sys.exit()
      elif opt in ("-i", "--ifile"):
         inputfile = arg
      elif opt in ("-o", "--ofile"):
         outputfile = arg
   print '������ļ�Ϊ��', inputfile
   print '������ļ�Ϊ��', outputfile

if __name__ == "__main__":
   main(sys.argv[1:])


$ python test.py -h
usage: test.py -i <inputfile> -o <outputfile>

$ python test.py -i inputfile -o outputfile
������ļ�Ϊ�� inputfile
������ļ�Ϊ�� outputfile

