"""
This is the class to handle all the DEIMOS specific attributes
DEIMOS specific DR techniques can be added to it in the future

12/14/2017 M. Brown - Created initial file
"""

import instrument
import datetime as dt
from common import *
import numpy as np
from astropy.io import fits
from scipy import ndimage

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from astropy.visualization import ZScaleInterval, AsinhStretch, SinhStretch
from astropy.visualization.mpl_normalize import ImageNormalize
from mpl_toolkits.axes_grid1 import ImageGrid

class Deimos(instrument.Instrument):

    def __init__(self, instr, utDate, rootDir, log=None):

        # Call the parent init to get all the shared variables
        super().__init__(instr, utDate, rootDir, log)


        # Set any unique keyword index values here
        self.keywordMap['OFNAME']       = 'DATAFILE'        
        self.keywordMap['FRAMENO']      = ''


        # Other vars that subclass can overwrite
        self.endTime = '20:00:00'   # 24 hour period start/end time (UT)
        
        # Skip warnings for these FCS-only keywords
        self.keywordSkips   = ['EXPOSURE', 'MPPMODE', 'NAXIS1', 'NAXIS2']
        self.keywordSkips.extend(['NUMAMPS', 'OBSNUM', 'PREPIX', 'SFRAMENO'])
        self.keywordSkips.extend(['SHUTSTAT', 'SOBJECT', 'SOBSTYPE', 'SOUTDIR'])
        self.keywordSkips.extend(['SOUTFILE', 'STTIME', 'SYNOPFMT', 'SYNOPSIS'])
        self.keywordSkips.extend(['TODISK', 'VOFFSET0', 'VOFFSET1', 'WINDOW', 'YFLIP'])

        # Generate the paths to the DEIMOS datadisk accounts
        self.sdataList = self.get_dir_list()


        # """
        # Values not included in superclass, specific to DEIMOS
        # """
        # # add the FCSIMGFI config file for deimos
        # self.fcsimgfi = 'FCSIMGFI'
        self.gratingList = {}
        self.gratingList['600ZD'] = {'wave':7500, 'dispersion':0.65, 'length':5300}
        self.gratingList['830G']  = {'wave':8640, 'dispersion':0.47, 'length':3840}
        self.gratingList['900ZD'] = {'wave':5500, 'dispersion':0.44, 'length':3530}
        self.gratingList['1200G'] = {'wave':7760, 'dispersion':0.33, 'length':2630}
        self.gratingList['1200B'] = {'wave':4500, 'dispersion':0.33, 'length':2630}
        # Filter list for imaging wavelengths
        self.filterList = {}
        self.filterList['B']      = {'blue':4200, 'cntr':4400, 'red':4600}
        self.filterList['V']      = {'blue':5150, 'cntr':5450, 'red':5750}
        self.filterList['R']      = {'blue':6100, 'cntr':6500, 'red':6900}
        self.filterList['I']      = {'blue':7600, 'cntr':8400, 'red':9200}
        self.filterList['Z']      = {'blue':8600, 'cntr':9100, 'red':9600}
        self.filterList['GG400']  = {'blue':4000, 'cntr':7250, 'red':10500}
        self.filterList['GG455']  = {'blue':4550, 'cntr':7525, 'red':10500}
        self.filterList['GG495']  = {'blue':4950, 'cntr':7725, 'red':10500}
        self.filterList['OG550']  = {'blue':5500, 'cntr':8000, 'red':10500}
        self.filterList['NG8560'] = {'blue':8400, 'cntr':8550, 'red':8700}
        self.filterList['NG8580'] = {'blue':8550, 'cntr':8600, 'red':8650}


    def run_dqa_checks(self, progData):
        '''
        Run all DQA check unique to this instrument
        '''

        ok = True
        if ok: ok = self.set_instr()
        if ok: ok = self.set_fcs_date_time()
        if ok: ok = self.set_dateObs()
        if ok: ok = self.set_ut()
        if ok: ok = self.set_koaimtyp()
        if ok: ok = self.set_koaid()
        if ok: ok = self.set_fcskoaid()
        if ok: ok = self.set_ofName()
        if ok: ok = self.set_semester()
        if ok: ok = self.set_prog_info(progData)
        if ok: ok = self.set_propint(progData)
        if ok: ok = self.set_datlevel(0)
        if ok: ok = self.set_weather_keywords()
        if ok: ok = self.set_oa()
        if ok: ok = self.set_dqa_vers()
        if ok: ok = self.set_dqa_date()
        if ok: ok = self.set_camera()
        if ok: ok = self.set_filter()
        if ok: ok = self.set_mjd()
        if ok: ok = self.set_obsmode()
        if ok: ok = self.set_nexten()
        if ok: ok = self.set_detsec()
        if ok: ok = self.set_npixsat(satVal=65535.0)
        if ok: ok = self.set_wavelengths()
        if ok: ok = self.set_spatscal()
        if ok: ok = self.set_dispscal()
        if ok: ok = self.set_specres()

        return ok


    def get_dir_list(self):
        """
        Function to generate the paths to all the DEIMOS accounts, including engineering
        Returns the list of paths
        """
        dirs = []
        path = '/s/sdata100'
        for i in range(1,6):
            path2 = path + str(i)
            for j in range(1,21):
                path3 = path2 + '/deimos' + str(j)
                dirs.append(path3)
            path3 = path2 + '/dmoseng'
            dirs.append(path3)
        return dirs


    def get_prefix(self):
        '''
        Returns the KOAID prefix to use, either DE for a DEIMOS science/calibration
        exposure or DF for an FCS image.
        '''

        instr = self.get_instr()
        outdir = self.get_keyword('OUTDIR')
        
        if '/fcs' in outdir:
            prefix = 'DF'
        elif instr == 'deimos':
            prefix = 'DE'
        else:
            prefix = ''
        return prefix


    def set_fcs_date_time(self):
        '''
        For FCS images, set DATE-OBS and UTC from DATE
        '''

        if '/fcs' not in self.get_keyword('OUTDIR', default=''):
            return True

        dateVal = self.get_keyword('DATE', default='')
        if 'T' not in dateVal:
            return True

        dateobs, utc = dateVal.split('T')
        utc = f'{utc}.00'
        
        self.log.info('set_fcs_date_time: Setting DATE-OBS and UTC from DATE')
        self.set_keyword('DATE-OBS', dateobs, 'KOA: Created from DATE keyword value')
        self.set_keyword('UTC', utc, 'KOA: Created from DATE keyword value')
        
        return True


    def set_ofName(self):
        '''
        Sets OFNAME keyword from OUTFILE and FRAMENO
        '''

        outfile = self.get_keyword('OUTFILE', False)
        frameno = self.get_keyword('FRAMENO', False)
        if outfile == None or frameno == None:
            self.log.info('set_ofName: Could not detrermine OFNAME')
            ofname = ''
            return False
        
        frameno = str(frameno).zfill(4)
        ofName = ''.join((outfile, frameno, '.fits'))
        self.log.info('set_ofName: OFNAME = {}'.format(ofName))
        self.set_keyword('OFNAME', ofName, 'KOA: Original file name')

        return True


    def set_koaimtyp(self):
        '''
        Calls get_koaimtyp to determine image type. 
        Creates KOAIMTYP keyword.
        '''

        if '/fcs' in self.get_keyword('OUTDIR', default=''):
            koaimtyp = 'fcscal'
        else:
            koaimtyp = self.get_koaimtyp()

        # Warn if undefined
        if koaimtyp == 'undefined':
            self.log.info('set_koaimtyp: Could not determine KOAIMTYP value')

        # Create the keyword
        self.set_keyword('KOAIMTYP', koaimtyp, 'KOA: Image type')

        return True


    def get_koaimtyp(self):
        '''
        Return image type based on the algorithm provided by SA
        '''

        # Get relevant keywords from header
        obstype  = self.get_keyword('OBSTYPE', default='').lower()
        slmsknam = self.get_keyword('SLMSKNAM', default='').lower()
        hatchpos = self.get_keyword('HATCHPOS', default='').lower()
        flimagin = self.get_keyword('FLIMAGIN', default='').lower()
        flspectr = self.get_keyword('FLSPECTR', default='').lower()
        lamps    = self.get_keyword('LAMPS', default='').lower()
        gratepos = self.get_keyword('GRATEPOS')

        # if obstype is 'bias' we have a bias
        if obstype == 'bias':
            return 'bias'

        # if obsmode is 'dark' we have a dark
        if obstype == 'dark':
            return 'dark'

        # if slmsknam contains 'goh' we have a focus image
        if slmsknam.startswith('goh'):
            return 'focus'

        # if hatch is closed and lamps are quartz, then flat
        if hatchpos == 'closed' and 'qz' in lamps:
            return 'flatlamp'

        # if hatch is open and flimagin or flspectr are on, then flat
        if hatchpos == 'open' and (flimagin == 'on' or flspectr == 'on'):
            return 'flatlamp'

        # if lamps are not off/qz and grating position is 3 or 4, then arc
        if hatchpos == 'closed' and ('off' not in lamps and 'qz' not in lamps)\
           and (gratepos == 3 or gratepos == 4):
            return 'arclamp'

        # if tracking then we must have an object science image
        # otherwise, don't know what it is
        if hatchpos == 'open':
            return 'object'

        # check for fcs image
        outdir = self.get_keyword('OUTDIR', default='')
        if 'fcs' in outdir:
            return 'fcscal'

        return 'undefined'


    def set_camera(self):
        '''
        Adds the keyword CAMERA to the header and sets its value to DEIMOS
        '''
        
        camera = self.get_keyword('CAMERA', False)
        if camera == None:
            self.log.info('set_camera: Adding CAMERA keyword')
            self.set_keyword('CAMERA', 'DEIMOS', 'KOA: Camera name')

        return True


    def set_filter(self):
        '''
        Adds the keyword FILTER to the header and sets its value to be the 
        same as the DWFILNAM keyword.
        '''

        filter = self.get_keyword('DWFILNAM', False)
        if filter == None:
            self.log.info('set_filter: Could not set filter, no DWFILNAM value')
        else:
            self.log.info('set_filter: Adding FILTER keyword')
            self.set_keyword('FILTER', filter, 'KOA: Filter name')
        
        return True


    def set_mjd(self):
        '''
        Adds the keyword MJD to the header and sets its value equal to the 
        MJD-OBS keyword.  MJD is the numeric respresentation of MJD-OBS.
        '''

        mjd = self.get_keyword('MJD-OBS', False)
        if mjd == None:
            self.log.info('set_mjd: Could not set MJD, no MJD-OBS value')
        else:
            self.log.info('set_mjd: Adding MJD keyword')
            self.set_keyword('MJD', float(mjd), 'KOA: Modified julian day')
        
        return True


    def set_obsmode(self):
        '''
        Adds the keyword OBSMODE to the header.
        
        UNKNOWN if:  GRATENAM = "Unknown", "None", or (blank)
        IMAGING if:  GRATENAM = "Mirror"
                     OR
                     ( GRATEPOS = 3 and G3TLTNAM = "Zeroth_Order"
                       OR
                       GRATEPOS = 4 and G4TLTNAM = "Zeroth_Order"
                     )
        LONGSLIT if: GRATENAM != ["Mirror", "Unknown", "None", (blank)]
                     AND
                     SLMSKNAM contains "LVM*" or "Long*"
        MOS if:      GRATENAM != ["Mirror", "Unknown", "None", (blank)]
                     AND
                     SLMSKNAM != ["LVM*", "Long*"]
        '''

        self.log.info('set_obsmode: Adding OBSMODE keyword')
        
        obsmode = 'null'
        
        gratname = self.get_keyword('GRATENAM', default='').lower()
        gratepos = self.get_keyword('GRATEPOS', default=0)

        if gratname in ['', 'unknown', 'none']:
            obsmode = 'unknown'
        elif gratname == 'mirror':
            obsmode = 'imaging'
        elif int(gratepos) == 3 or int(gratepos) == 4:
            key = f'G{int(gratepos)}TLTNAM'
            tilt = self.get_keyword(key, default='').lower()
            if tilt == 'zeroth_order':
                obsmode = 'imaging'
#            else:
#                obsmode = 'imaging'
            else:
                slmsknam = self.get_keyword('SLMSKNAM', default='')
                if slmsknam.startswith('LVM') or slmsknam.startswith('Long'):
                    obsmode = 'longslit'
                else:
                    obsmode = 'mos'

        self.set_keyword('OBSMODE', obsmode, 'KOA: Observing mode')

        return True


    def set_nexten(self):
        '''
        Adds the NEXTEN keyword and sets its value to the number of
        imaging extensions for this file.
        '''

        self.log.info('set_nexten: Adding NEXTEN keyword')
        self.set_keyword('NEXTEN', int(len(self.fitsHdu))-1, 'KOA: Number of image extensions')

        return True


    def set_detsec(self):
        '''
        Adds the DETSEC## keywords to the primary header.  Value of the
        keyword is set equal to the DETSEC keyword value from the image
        headers.  ## = 01 to 16.
        '''

        self.log.info('set_detsec: Adding DETSEC## keywords')

        maxExtensions = 16
        for i in range(1, maxExtensions+1):
            key = f'DETSEC{str(i).zfill(2)}'
            detsec = 'null'
            if i < len(self.fitsHdu):
                try:
                    detsec = self.fitsHdu[i].header['DETSEC']
                except:
                    pass
            comment = f'KOA: Mosaic detector section for HDU{str(i).zfill(2)}'
            self.set_keyword(key, detsec, comment)

        return True


    def set_npixsat(self, satVal=None):
        '''
        Determines number of saturated pixels and adds NPIXSAT to header
        NPIXSAT is the sum of all image extensions.
        '''

        self.log.info('set_npixsat: setting pixel saturation keyword value')

        if satVal == None:
            satVal = self.get_keyword('SATURATE')

        if satVal == None:
            self.log.warning("set_npixsat: Could not find SATURATE keyword")
        else:
            nPixSat = 0
            for ext in range(1, len(self.fitsHdu)):
                image = self.fitsHdu[ext].data
                if 'ndarray' not in str(type(image)): continue
                pixSat = image[np.where(image >= satVal)]
                nPixSat += len(image[np.where(image >= satVal)])

            self.set_keyword('NPIXSAT', nPixSat, 'KOA: Number of saturated pixels')

        return True


    def set_wavelengths(self):
        '''
        Adds wavelength keywords.
        '''

        waveblue = wavecntr = wavered = 'null'

        # Is this an image or spectrum?
        obsmode = self.get_keyword('OBSMODE')
        if obsmode == 'imaging':
            filter = self.get_keyword('FILTER', default='').strip()
            if filter in self.filterList.keys():
                waveblue = self.filterList[filter]['blue']
                wavecntr = self.filterList[filter]['cntr']
                wavered  = self.filterList[filter]['red']

        elif obsmode in ['longslit', 'mos']:
            gratepos = self.get_keyword('GRATEPOS')
            waveKey = f'G{gratepos}TLTWAV'
            grating = self.get_keyword('GRATENAM')
            if grating in self.gratingList.keys():
                wavecntr = int(round(self.get_keyword(waveKey), -1))
                delta = self.gratingList[grating]['length']/2
                waveblue = int(round(wavecntr - delta, -1))
                wavered = int(round(wavecntr + delta, -1))

        else:
            pass

        self.set_keyword('WAVEBLUE', waveblue, 'KOA: Blue end wavelength')
        self.set_keyword('WAVECNTR', wavecntr, 'KOA: Center wavelength')
        self.set_keyword('WAVERED' , wavered, 'KOA: Red end wavelength')

        return True


    def set_spatscal(self):
        '''
        Populates SPATSCAL
        '''
        
        self.set_keyword('SPATSCAL', 0.1185, 'KOA: CCD spatial pixel scale')
        return True


    def set_dispscal(self):
        '''
        Populates DISPSCAL
        '''

        dispscal = 'null'
        com = ''

        obsmode = self.get_keyword('OBSMODE')
        spatscal = self.get_keyword('SPATSCAL')
        if obsmode == 'imaging':
            dispscal = spatscal
            com = ' (arcsec/pix)'
        elif obsmode in ['longslit', 'mos']:
            grating = self.get_keyword('GRATENAM')
            if grating in self.gratingList.keys():
                dispscal = self.gratingList[grating]['dispersion']
                com = ' (A/pix)'

        self.set_keyword('DISPSCAL', dispscal, f'KOA: CCD dispersion pixel scale{com}')
        return True


    def set_specres(self):
        '''
        Calculates the spectral resolution and add SPECRES to header
        '''

        specres = 'null'

        spatscal = self.get_keyword('SPATSCAL')
        grating = self.get_keyword('GRATENAM')

        if grating in self.gratingList.keys():
            specres = (self.gratingList[grating]['wave']*spatscal)/self.gratingList[grating]['dispersion']
            specres = round(specres, -1)

        self.set_keyword('SPECRES', specres, 'KOA: nominal spectral resolution')

        return True


    def create_jpg_from_fits(self, fits_filepath, outdir):
        '''
        Overriding instrument default function
        Tile images horizontally in order from left to right.
        Use DETSEC keyword to figure out data order/position
        '''

        #open
        hdus = fits.open(fits_filepath, ignore_missing_end=True)

        #needed hdr vals
        hdr0 = hdus[0].header

        if hdr0['KOAID'].startswith('DF'):
            super().create_jpg_from_fits(fits_filepath, outdir)
            return
            
        binning  = hdr0['BINNING'].split(',')
        precol   = int(hdr0['PRECOL'])   // int(binning[0])
        postpix  = int(hdr0['POSTPIX'])  // int(binning[0])
        preline  = int(hdr0['PRELINE'])  // int(binning[1])
        postline = int(hdr0['POSTLINE']) // int(binning[1])

        #get extension order (uses DETSEC keyword)
        ext_order = Deimos.get_ext_data_order(hdus)
        assert ext_order, "ERROR: Could not determine extended data order"

        #loop thru extended headers in order, create png and add to list in order
        interval = ZScaleInterval()
        vmin = None
        vmax = None
#        alldata = None
        # DEIMOS has 2 rows of 4 CCDs each
        alldata = [[], []]
        for row, extData in enumerate(ext_order):
            if len(extData) == 0: continue
            for i, ext in enumerate(extData):
                data = hdus[ext].data
                hdr  = hdus[ext].header
                if 'ndarray' not in str(type(data)): continue

                #calc bias array from postpix area
                sh = data.shape
                x1 = 0
                x2 = sh[0]
                y1 = sh[1] - postpix + 1
                y2 = sh[1] - 1
                bias = np.median(data[x1:x2, y1:y2], axis=1)
                bias = np.array(bias, dtype=np.int64)

                #subtract bias
                data = data - bias[:,None]

                #get min max of each ext (not including pre/post pixels)
                #NOTE: using sample box that is 90% of full area
                #todo: should we take an average min/max of each ext for balancing?
                sh = data.shape
                x1 = int(preline          + (sh[0] * 0.10))
                x2 = int(sh[0] - postline - (sh[0] * 0.10))
                y1 = int(precol           + (sh[1] * 0.10))
                y2 = int(sh[1] - postpix  - (sh[1] * 0.10))
                tmp_vmin, tmp_vmax = interval.get_limits(data[x1:x2, y1:y2])
                if vmin == None or tmp_vmin < vmin: vmin = tmp_vmin
                if vmax == None or tmp_vmax > vmax: vmax = tmp_vmax
                if vmin < 0: vmin = 0

                #remove pre/post pix columns
                data = data[:,precol:data.shape[1]-postpix]

                #flip data left/right
                #NOTE: This should come after removing pre/post pixels
                ds = Deimos.get_detsec_data(hdr['DETSEC'])
                if ds and ds[0] > ds[1]:
                    data = np.fliplr(data)
                if ds and ds[2] > ds[3]:
                    data = np.flipud(data)

                #concatenate horizontally
                if i==0:
                    alldata[row] = data
                else   :
                    alldata[row] = np.append(alldata[row], data, axis=1)

        # If alldata has 2 rows, then vertically stack them
        # else take the one row

        s0 = len(alldata[0])
        s1 = len(alldata[1])

        if s0 > 0 and s1 > 0:
            alldata = np.concatenate((alldata[0], alldata[1]), axis=0)
            # Need to rotate final stitched image
            alldata = ndimage.rotate(alldata, -90, axes=(0, 1))
        elif s0 > 0:
            alldata = alldata[0]
        elif s1 > 0:
            alldata = alldata[1]

        #filepath vars
        basename = os.path.basename(fits_filepath).replace('.fits', '')
        out_filepath = f'{outdir}/{basename}.jpg'

        #bring in min/max by 2% to help ignore large areas of black or overexposed spots
        #todo: this does not achieve what we want
        # minmax_adjust = 0.02
        # vmin += int((vmax - vmin) * minmax_adjust)
        # vmax -= int((vmax - vmin) * minmax_adjust)

        #normalize, stretch and create jpg
        norm = ImageNormalize(vmin=vmin, vmax=vmax, stretch=AsinhStretch())
        dpi = 100
        width_inches  = alldata.shape[1] / dpi
        height_inches = alldata.shape[0] / dpi
        fig = plt.figure(figsize=(width_inches, height_inches), frameon=False, dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1]) #this forces no border padding; bbox_inches='tight' doesn't really work
        plt.axis('off')
        plt.imshow(alldata, cmap='gray', origin='lower', norm=norm)
        # DEIMOS jpegs are large, let's reduce the size using dpi (default is 100)
        plt.savefig(out_filepath, quality=92, dpi=(50))
        plt.close()


    @staticmethod
    def get_ext_data_order(hdus):
        '''
        Use DETSEC keyword to figure out true order of extension data for horizontal tiling
        '''
        key_orders = [{}, {}]
        for i in range(1, len(hdus)):
            arrRow = 0
            try:
                ds = Deimos.get_detsec_data(hdus[i].header['DETSEC'])
                if not ds: return None
                if ds[2] > 4096 or ds[3] > 4096: arrRow = 1
                key_orders[arrRow][ds[0]] = i
            except:
                pass

        # DEIMOS can have 2 rows of 4 CCDs each
        orders = [[], []]
        for num, entry in enumerate(key_orders):
            for key in sorted(entry):
                orders[num].append(entry[key])

        return orders


    @staticmethod
    def get_detsec_data(detsec):
        '''
        Parse DETSEC string for x1, x2, y1, y2
        '''
        match = re.search( r'(-?\d+):(-?\d+),(-?\d+):(-?\d+)', detsec)
        if not match:
            return None
        else:
            x1 = int(match.groups(1)[0])
            x2 = int(match.groups(1)[1])
            y1 = int(match.groups(1)[2])
            y2 = int(match.groups(1)[3])
            return [x1, x2, y1, y2]


    def create_fcs_list(self, locateFile):
        '''
        Creates self.fcsFiles for use in set_fcskoaid()
        '''

        self.fcsFiles = {}
        with open(locateFile, 'r') as lf:
            for line in lf:
                file = line.strip()
                self.set_fits_file(file)
                self.set_utc()
                self.set_dateObs()
                koaid, result = self.make_koaid()
                if koaid.startswith('DF'):
                    self.fcsFiles[file.split('/')[-1]] = koaid


    def set_fcskoaid(self):
        '''
        Populates FCSKOAID with the associated FCS file
        '''

        fcs = self.get_keyword('FCSIMGFI', default='')
        fcs = fcs.split('/')[-1]
        fcskoaid = ''
        if fcs in self.fcsFiles.keys():
            fcskoaid = self.fcsFiles[fcs]
        self.set_keyword('FCSKOAID', fcskoaid, 'KOA: associated fcs file')

        return True

    def check_filetime_vs_window(self, filename):
        '''
        Verify that FCS file is taken within the 24 hour defined time window.
        This avoids transferring FCS files with duplicate KOAID to the DB.
        '''
        if 'DE' in self.fitsHeader.get('KOAID'):
            return True

        tm_format = "%Y-%m-%d %H:%M:%S"
        endTimeStr = self.utDate + ' ' + self.endTime
        endTime = dt.datetime.strptime(endTimeStr, tm_format)
        yesterTime = endTime - dt.timedelta(days=1)

        fileTime = os.path.getmtime(filename)
        fileTime = dt.datetime.utcfromtimestamp(fileTime).strftime(tm_format)
        fileTime = dt.datetime.strptime(fileTime, tm_format)

        if yesterTime < fileTime < endTime:
            return True
        
        log_msg = f'FCS file: {filename} is outside 24 hr period and will be '
        log_msg += f'excluded from the archiving process.'
        self.log.info(log_msg)
        
        return False

