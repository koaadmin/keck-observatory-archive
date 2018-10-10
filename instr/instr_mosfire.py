'''
This is the class to handle all the MOSFIRE specific attributes
MOSFIRE specific DR techniques can be added to it in the future

12/14/2017 M. Brown - Created initial file
'''

import instrument
import datetime as dt
from common import *


class Mosfire(instrument.Instrument):

    def __init__(self, instr, utDate, rootDir, log=None):

        # Call the parent init to get all the shared variables
        super().__init__(instr, utDate, rootDir, log)


        # Set any unique keyword index values here
        self.keywordMap['OFNAME']       = 'DATAFILE'        
        self.keywordMap['FRAMENO']      = 'FRAMENUM'


        # Other vars that subclass can overwrite
        self.endTime = '20:00:00'   # 24 hour period start/end time (UT)


        # Generate the paths to the NIRES datadisk accounts
        self.sdataList = self.get_dir_list()



    def run_dqa_checks(self, progData):
        '''
        Run all DQA checks unique to this instrument.
        '''

        #todo: finish this
        #todo: check that all of these do not need a subclass version if base class func was used.
        ok = True
        if ok: ok = self.check_instr()
        if ok: ok = self.set_dateObs()
        if ok: ok = self.set_utc()
        if ok: ok = self.set_elaptime()
        if ok: ok = self.set_koaimtyp()
        if ok: ok = self.set_koaid()
        if ok: ok = self.set_ut()
        if ok: ok = self.set_frameno()
        if ok: ok = self.set_ofName()
        if ok: ok = self.set_semester()
        if ok: ok = self.set_prog_info(progData)
        if ok: ok = self.set_propint(progData)
        # if ok: ok = self.set_wavelengths()
        # if ok: ok = self.set_specres()
        if ok: ok = self.set_weather_keywords()
        if ok: ok = self.set_datlevel(0)
        # if ok: ok = self.set_filter()
        # if ok: ok = self.set_slit_dims()
        # if ok: ok = self.set_spatscal()
        # if ok: ok = self.set_dispscal()
        if ok: ok = self.set_image_stats_keywords()
        if ok: ok = self.set_npixsat()
        if ok: ok = self.set_oa()
        if ok: ok = self.set_dqa_date()
        if ok: ok = self.set_dqa_vers()
        return ok



    def get_dir_list(self):
        '''
        Function to generate the paths to all the MOSFIRE accounts, including engineering
        Returns the list of paths
        '''
        dirs = []
        path = '/s/sdata1300'
        joinSeq = (path, '/mosfire')
        path2 = ''.join(joinSeq)
        dirs.append(path2)
        for i in range(1,10):
            joinSeq = (path, '/mosfire', str(i))
            path2 = ''.join(joinSeq)
            dirs.append(path2)
        joinSeq = (path, '/moseng')
        path2 = ''.join(joinSeq)
        dirs.append(path2)
        return dirs


    def get_prefix(self):

        instr = self.get_instr()
        if instr == 'mosfire': prefix = 'MF'
        else                 : prefix = ''
        return prefix


    def set_koaimtyp(self):
        '''
        Fixes missing KOAIMTYP keyword.
        '''

        #todo

        koaimtyp = 'undefined'


        #update keyword
        self.set_keyword('KOAIMTYP', koaimtyp, 'KOA: Image type')
        return True


    def set_elaptime(self):
        '''
        Fixes missing ELAPTIME keyword.
        '''

        self.log.info('set_elaptime: determining ELAPTIME from ITIME/COADDS')

        #skip if it exists
        if self.get_keyword('ELAPTIME', False) != None: return True

        #get necessary keywords
        itime  = self.get_keyword('ITIME')
        coadds = self.get_keyword('COADDS')
        if (itime == None or coadds == None):
            self.log.error('set_elaptime: ITIME and COADDS values needed to set ELAPTIME')
            return False

        #update val
        elaptime = itime * coadds
        self.set_keyword('ELAPTIME', elaptime, 'KOA: Total integration time')
        return True


    def is_science(self):
        '''
        Returns true if header indicates science data was taken.
        '''

        #todo: is this right?

        koaimtyp = self.get_keyword('KOAIMTYP')
        if koaimtyp == 'object' : return True
        else                    : return False


    def set_frameno(self):
        """
        Adds FRAMENO keyword to header if it doesn't exist
        """
        # todo: Is all this needed for MOSFIRE too like NIRES?  If so, make commo?

        self.log.info('set_frameno: setting FRAMNO keyword value from FRAMENUM')

        #skip if it exists
        if self.get_keyword('FRAMENO', False) != None: return True

        #get value
        #NOTE: If FRAMENO doesn't exist, derive from DATAFILE
        frameno = self.get_keyword('FRAMENUM')
        if (frameno == None): 

            datafile = self.get_keyword('DATAFILE')
            if (datafile == None): 
                self.log.error('set_frameno: cannot find value for FRAMENO')
                return False

            frameno = datafile.replace('.fits', '')
            num = frameno.rfind('_') + 1
            frameno = frameno[num:]
            frameno = int(frameno)

        #update
        self.set_keyword('FRAMENO', frameno, 'KOA: Image frame number')
        return True


    def set_ofName(self):
        """
        Adds OFNAME keyword to header 
        """

        self.log.info('set_ofName: setting OFNAME keyword value')

        #get value
        ofName = self.get_keyword('OFNAME')
        if (ofName == None): 
            self.log.error('set_ofName: cannot find value for OFNAME')
            return False

        #add *.fits to output if it does not exist (to fix old files)
        if (ofName.endswith('.fits') == False) : ofName += '.fits'

        #update
        self.set_keyword('OFNAME', ofName, 'KOA: Original file name')
        return True
