"""
  This script consolidates all the pieces of the KOA data quality
  assessment into one place. Upon completion, it should populate the
  process directory with the final FITS files, in some cases adding 
  header keywords where necessary.

  Usage: dep_dqa(instrObj, tpx)

  Original scripts written by Jeff Mader and Jennifer Holt
  Ported to Python3 by Matthew Brown and Josh Riley
"""
import os
import sys
import getProgInfo as gpi
from create_prog import *
import shutil
from common import *
from datetime import datetime as dt
import metadata
import re

def dep_dqa(instrObj, tpx=0):
    """
    This function will analyze the FITS file to determine if they will be
    archived and if they need modifications or additions to their headers.

    @type instrObj: instrument
    @param instr: The instrument object
    """

    #define vars to use throughout
    instr  = instrObj.instr
    utDate = instrObj.utDate
    log    = instrObj.log
    dirs   = instrObj.dirs
    utDateDir = instrObj.utDateDir
    sciFiles = 0
    inFiles = []
    outFiles = []
    procFiles = []
    semids = []
    extraMeta = {}
    dqaFile = dirs['stage'] +'/dep_dqa' + instr +'.txt'


    #Log start
    log.info('dep_dqa.py started for {} {}'.format(instr, utDate))


    #todo: check for existing output files and error out with warning?


    # Error if locate file does not exist (required input file)
    locateFile = dirs['stage'] + '/dep_locate' + instr + '.txt'
    if not os.path.exists(locateFile):
        raise Exception('dep_dqa.py: locate input file does not exist.  EXITING.')
        return
        

    # Read the list of FITS files
    files = []
    with open(locateFile, 'r') as locatelist:
        for line in locatelist:
            files.append(line.strip())


    #if no files, then exit out
    if len(files) == 0 :
        notify_zero_files(instrObj, dqaFile, tpx, log)
        return


    #determine program info
    create_prog(instrObj)
    progData = gpi.getProgInfo(utDate, instr, dirs['stage'], log)


    # Loop through each entry in input_list
    log.info('dep_dqa.py: Processing {} files'.format(len(files)))
    for filename in files:

        log.info('dep_dqa.py input file is {}'.format(filename))

        #Set current file to work on and run dqa checks, etc
        ok = True
        if ok: ok = instrObj.set_fits_file(filename)
        if ok: ok = instrObj.run_dqa_checks(progData)
        if ok: ok = check_koaid(instrObj, outFiles, log)
        if ok: ok = instrObj.write_lev0_fits_file()
        if ok: ok = instrObj.make_jpg()

 
        #If any of these steps return false then copy to udf and skip
        if (not ok): 
            log.info('FITS file is UDF.  Copying {} to {}'.format(filename, dirs['udf']))
            shutil.copy2(filename, dirs['udf']);
            continue

        #keep list of good fits filenames
        procFiles.append(instrObj.fitsFilepath)
        inFiles.append(os.path.basename(instrObj.fitsFilepath))
        outFiles.append(instrObj.fitsHeader.get('KOAID'))
        semids.append(instrObj.get_semid())

        #stats
        if instrObj.is_science(): sciFiles += 1

        #deal with extra metadata
        koaid = instrObj.fitsHeader.get('KOAID')
        extraMeta[koaid] = instrObj.extraMeta


    #if no files passed DQA, then exit out
    if len(outFiles) == 0 :
        notify_zero_files(instrObj, dqaFile, tpx, log)
        return


    #log num files passed DQA and write out list to file
    log.info('dep_dqa.py: {} files passed DQA'.format(len(procFiles)))
    with open(dqaFile, 'w') as f:
        for path in procFiles:
            f.write(path + '\n')


    #Create yyyymmdd.filelist.table
    fltFile = dirs['lev0'] + '/' + utDateDir + '.filelist.table'
    with open(fltFile, 'w') as fp:
        for i in range(len(inFiles)):
            fp.write(inFiles[i] + ' ' + outFiles[i] + "\n")
        fp.write("    " + str(len(inFiles)) + ' Total FITS files\n')


    #create metadata file
    log.info('make_metadata.py started for {} {} UT'.format(instr.upper(), utDate))
    tablesDir = instrObj.metadataTablesDir
    ymd = utDate.replace('-', '')
    metaOutFile =  dirs['lev0'] + '/' + ymd + '.metadata.table'
    keywordsDefFile = tablesDir + '/keywords.format.' + instr
    metadata.make_metadata(keywordsDefFile, metaOutFile, dirs['lev0'], extraMeta, log)    


    #Create yyyymmdd.FITS.md5sum.table
    md5Outfile = dirs['lev0'] + '/' + utDateDir + '.FITS.md5sum.table'
    log.info('dep_dqa.py creating {}'.format(md5Outfile))
    make_dir_md5_table(dirs['lev0'], ".fits", md5Outfile)


    #Create yyyymmdd.JPEG.md5sum.table
    md5Outfile = dirs['lev0'] + '/' + utDateDir + '.JPEG.md5sum.table'
    log.info('dep_dqa.py creating {}'.format(md5Outfile))
    make_dir_md5_table(dirs['lev0'], ".jpg", md5Outfile)


    #gzip the fits files
    log.info('dep_dqa.py gzipping fits files in {}'.format(dirs['lev0']))
    import gzip
    for file in os.listdir(dirs['lev0']):
        if file.endswith('.fits'): 
            in_path = dirs['lev0'] + '/' + file
            out_path = in_path + '.gz'
            with open(in_path, 'rb') as fIn:
                with gzip.open(out_path, 'wb', compresslevel=5) as fOut:
                    shutil.copyfileobj(fIn, fOut)
                    os.remove(in_path)


    #get sdata number lists and PI list strings
    piList = get_tpx_pi_str(progData)
    sdataList = get_tpx_sdata_str(progData)


    #update TPX: archive ready
    if tpx:
        log.info('dep_dqa.py: updating tpx DB records')
        utcTimestamp = dt.utcnow().strftime("%Y%m%d %H:%M")
        update_koatpx(instr, utDate, 'files_arch', str(len(procFiles)), log)
        update_koatpx(instr, utDate, 'pi', piList, log)
        update_koatpx(instr, utDate, 'sdata', sdataList, log)
        update_koatpx(instr, utDate, 'sci_files', str(sciFiles), log)
        update_koatpx(instr, utDate, 'arch_stat', 'DONE', log)
        update_koatpx(instr, utDate, 'arch_time', utcTimestamp, log)       
        update_koatpx(instr, utDate, 'size', get_directory_size(dirs['output']), log)


    #update koapi_send for all unique semids
    if tpx:
        check_koapi_send(semids, instrObj.utDate, log)


    #log success
    log.info('dep_dqa.py DQA Successful for {}'.format(instr))



def check_koapi_send(semids, utDate, log):
    '''
    Sends all unique semids processed in DQA to KOA api to flag semids
    for needing an email sent to PI that there data has been archived
    '''

    #create needed api vars
    import configparser
    config = configparser.ConfigParser()
    config.read('config.live.ini')

    import hashlib
    user = os.getlogin()
    myHash = hashlib.md5(user.encode('utf-8')).hexdigest()

    #loops thru semids, skipping duplicates
    processed = []
    for semid in semids:

        if semid in processed: continue

        #check if we should update koapi_send
        semester, progid = semid.split('_')
        if progid == 'NONE' or progid == 'null' or progid == 'ENG' or progid == '':
            continue;
        if progid == None or semester == None:
            continue;

        #koa api url
        url = config['API']['koaapi']
        url += 'cmd=updateKoapiSend'
        url += '&utdate=' + utDate
        url += '&semid='  + semid
        url += '&hash='   + myHash

        #call and check results
        log.info('check_koapi_send: calling koa api url: {}'.format(url))
        result = url_get(url)
        if result == None or result == 'false':
            log.warning('check_koapi_send failed')

        processed.append(semid)



def check_koaid(instrObj, koaidList, log):

    #sanity check
    koaid = instrObj.fitsHeader.get('KOAID')
    if (koaid == False or koaid == None):
        log.error('dep_dqa.py: BAD KOAID "{}" found for {}'.format(koaid, instrObj.fitsFilepath))
        return False

    #check for duplicates
    if (koaid in koaidList):
        log.error('dep_dqa.py: DUPLICATE KOAID "{}" found for {}'.format(koaid, instrObj.fitsFilepath))
        return False

    #check that date and time extracted from generated KOAID falls within our 24-hour processing datetime range.
    #NOTE: Only checking outside of 1 day difference b/c file write time can cause this to trigger incorrectly
    prefix, kdate, ktime, postfix = koaid.split('.')
    hours, minutes, seconds = instrObj.endTime.split(":") 
    endTimeSec = float(hours) * 3600.0 + float(minutes)*60.0 + float(seconds)
    idate = instrObj.utDate.replace('/', '-').replace('-', '')

    a = dt.strptime(kdate[:4]+'-'+kdate[4:6]+'-'+kdate[6:8], "%Y-%m-%d")
    b = dt.strptime(idate[:4]+'-'+idate[4:6]+'-'+idate[6:8], "%Y-%m-%d")
    delta = b - a
    delta = abs(delta.days)

    if (kdate != idate and delta > 1 and float(ktime) < endTimeSec):
        log.error('dep_dqa.py: KOAID "{}" has bad Date "{}" for file {}'.format(koaid, kdate, instrObj.fitsFilepath))
        return False

    return True



def notify_zero_files(instrObj, dqaFile, tpx, log):

    #log
    log.info('dep_dqa.py: 0 files output from DQA process.')

    #touch empty output file
    open(dqaFile, 'a').close()

    #tpx update
    if tpx:
        log.info('dep_dqa.py: updating tpx DB records')
        utcTimestamp = dt.utcnow().strftime("%Y%m%d %H:%M")
        update_koatpx(instrObj.instr, instrObj.utDate, 'arch_stat', 'DONE', log)
        update_koatpx(instrObj.instr, instrObj.utDate, 'arch_time', utcTimestamp, log)



def get_tpx_sdata_str(progData):
    '''
    Finds unique sdata directory numbers and creates string for DB
    ex: "123/456"
    '''
    items = []
    for row in progData:
        filepath = row['file']
        match = re.match( r'/sdata(.*?)/', filepath, re.I)
        if match:
            item = match.groups(1)[0]
            if item not in items:
                items.append(item)

    text = '/'.join(items)
    return text


def get_tpx_pi_str(progData):
    '''
    Finds unique PIs and creates string for DB
    ex: "Smith/Jones"
    '''
    items = []
    for row in progData:
        pi = row['progpi']
        if pi not in items:
            items.append(pi)

    text = '/'.join(items)
    return text

