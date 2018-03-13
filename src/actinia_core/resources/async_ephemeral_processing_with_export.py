# -*- coding: utf-8 -*-
"""
Asynchronous computation in specific temporary generated mapsets
with export of required map layers.
"""
import cPickle
import os
from flask import jsonify, make_response

from copy import deepcopy
from flask_restful_swagger_2 import swagger, Schema
from actinia_core.resources.async_ephemeral_processing import AsyncEphemeralProcessing
from actinia_core.resources.async_resource_base import AsyncEphemeralResourceBase
from actinia_core.resources.common.redis_interface import enqueue_job
from actinia_core.resources.common.process_object import Process
from actinia_core.resources.common.process_chain import ProcessChainModel
from actinia_core.resources.common.exceptions import AsyncProcessTermination
from actinia_core.resources.common.response_models import ProcessingResponseModel

__license__ = "GPLv3"
__author__     = "Sören Gebbert"
__copyright__  = "Copyright 2016, Sören Gebbert"
__maintainer__ = "Sören Gebbert"
__email__      = "soerengebbert@googlemail.com"


DESCR="""Execute a user defined process chain in an ephemeral database
and provide the generated resources as downloadable files via URL's. Minimum required user role: user.

The process chain is executed asynchronously. The provided status URL
in the response must be polled to gain information about the processing
progress and finishing status.

**Note**

    Make sure that the process chain definition identifies all raster, vector or
    space-time datasets correctly with name and mapset: name@mapset if you use
    data from other mapsets in the specified location.

    All required mapsets will be identified by analysing the input parameter
    of all module descriptions in the provided process chain
    and mounted read-only into the ephemeral database that is used for processing.

The persistent database will not be modified. The ephemeral database will be removed after processing.
Use the URL's provided in the finished response to download the resource that were specified
in the process chain for export.
"""


SCHEMA_DOC={
    'tags': ['ephemeral processing'],
    'description': DESCR,
    'consumes':['application/json'],
    'parameters': [
        {
            'name': 'location_name',
            'description': 'The location name that contains the data that should be processed',
            'required': True,
            'in': 'path',
            'type': 'string',
            'default': 'nc_spm_08'
        },
        {
            'name': 'process_chain',
            'description': 'The process chain that should be executed',
            'required': True,
            'in': 'body',
            'schema': ProcessChainModel
        }
    ],
    'responses': {
        '200': {
            'description': 'The result of the process chain execution',
            'schema':ProcessingResponseModel
        },
        '400': {
            'description':'The error message and a detailed log why process chain execution '
                          'did not succeeded',
            'schema':ProcessingResponseModel
        }
    }
 }


class AsyncEphemeralExportResource(AsyncEphemeralResourceBase):
    """
    This class represents a resource that runs asynchronous processing tasks in
    a temporary mapset and exports the computed results as geotiff files.
    """
    def __init__(self):
        AsyncEphemeralResourceBase.__init__(self)

    @swagger.doc(deepcopy(SCHEMA_DOC))
    def post(self, location_name):
        """Execute a user defined process chain in an ephemera location/mapset and store the processing results
        for download.
        """
        rdc = self.preprocess(has_json=True, location_name=location_name)
        rdc.set_storage_model_to_file()

        # RedisQueue approach
        enqueue_job(self.job_timeout, start_job, rdc)

        html_code, response_model = cPickle.loads(self.response_data)
        return make_response(jsonify(response_model), html_code)


class AsyncEphemeralExportS3Resource(AsyncEphemeralResourceBase):
    """
    This class represents a resource that runs asynchronous processing tasks in
    a temporary mapset and exports the computed results as geotiff files to the Amazon S3
    storage.
    """
    def __init__(self):
        AsyncEphemeralResourceBase.__init__(self)

    @swagger.doc(deepcopy(SCHEMA_DOC))
    def post(self, location_name):
        """Execute a user defined process chain in an ephemera location/mapset and store the processing result in an Amazon S3 bucket
        """
        rdc = self.preprocess(has_json=True, location_name=location_name)
        rdc.set_storage_model_to_s3()

        enqueue_job(self.job_timeout, start_job, rdc)

        html_code, response_model = cPickle.loads(self.response_data)
        return make_response(jsonify(response_model), html_code)


class AsyncEphemeralExportGCSResource(AsyncEphemeralResourceBase):
    """
    This class represents a resource that runs asynchronous processing tasks in
    a temporary mapset and exports the computed results as geotiff files to the
    Google Cloud Storage.
    """
    def __init__(self):
        AsyncEphemeralResourceBase.__init__(self)

    @swagger.doc(deepcopy(SCHEMA_DOC))
    def post(self, location_name):
        """Execute a user defined process chain in an ephemera location/mapset and store the processing result in an Google cloud storage bucket
        """
        rdc = self.preprocess(has_json=True, location_name=location_name)
        rdc.set_storage_model_to_gcs()

        enqueue_job(self.job_timeout, start_job, rdc)

        html_code, response_model = cPickle.loads(self.response_data)
        return make_response(jsonify(response_model), html_code)


def start_job(*args):
    processing = AsyncEphemeralProcessingWithExport(*args)
    processing.run()


class AsyncEphemeralProcessingWithExport(AsyncEphemeralProcessing):
    """
    This class processes GRASS data on the local machine in an temporary mapset
    and copies the exported results to a specific destination directory.

    The temporary mapset will be removed by this class when the processing finished
    and the results are stored in the dedicated directory.
    """
    def __init__(self, rdc):
        """
        Setup the variables of this class

        Args:
            rdc (ResourceDataContainer): The data container that contains all required variables for processing

        """
        AsyncEphemeralProcessing.__init__(self, rdc)
        # Create the storage interface to store the exported resources
        self.storage_interface = rdc.create_storage_interface()

    def _export_raster(self, raster_name,
                       format="GTiff",
                       additional_options=[],
                       use_raster_region=False):
        """Export a specific raster layer with r.out.gdal as GeoTiff.

        The result is stored in a temporary directory
        that is located in the temporary grass database.

        The region of the raster layer can be used for export. In this case a temporary region
        will be used for export, so that the original region of the mapset is not modified.

        Args:
            raster_name (str): The name of the raster layer
            format (str): GTiff
            additional_options (list): Unused
            use_raster_region (bool): Use the region of the raster layer for export

        Returns:
            tuple: A tuple (file_name, output_path)

        Raises:
            AsyncProcessError: If a GRASS module return status is not 0

        """
        # Export the layer
        prefix = ".tiff"
        if format == "GTiff":
            prefix = ".tiff"

        # Remove a potential mapset
        file_name = raster_name.split("@")[0] + prefix

        if use_raster_region is True:

            p = Process(exec_type="grass",
                             executable="g.region",
                             executable_params=["raster=%s"%raster_name, "-g"],
                             stdin_source=None)

            self._update_num_of_steps(1)
            self._run_module(p)

        # Save the file in the temporary directory of the temporary gisdb
        output_path = os.path.join(self.temp_file_path, file_name)

        module_name = "r.out.gdal"
        args = ["-fm", "input=%s"%raster_name, "format=%s"%format,
                "createopt=COMPRESS=LZW", "output=%s"%output_path]

        if additional_options:
            args.extend(additional_options)

        p = Process(exec_type="grass",
                         executable=module_name,
                         executable_params=args,
                         stdin_source=None)

        self._update_num_of_steps(1)
        self._run_module(p)

        return file_name, output_path

    def _export_vector(self, vector_name,
                       format="GML",
                       additional_options=[]):
        """Export a specific vector layer with v.out.ogr using a specific output format

        The result is stored in a temporary directory
        that is located in the temporary grass database.

        The resulting vector file will always be compressed using zip

        Args:
            vector_name (str): The name of the raster layer
            format (str): GML, GeoJSON, ESRI_Shapefile, SQLite, CSV
            additional_options (list): Unused

        Returns:
            tuple: A tuple (file_name, output_path)

        Raises:
            AsyncProcessError: If a GRASS module return status is not 0

        """
        # Export the layer
        prefix = ".gml"
        if format == "GML":
            prefix = ".gml"
        if format == "GeoJSON":
            prefix = ".json"
        if format == "ESRI_Shapefile":
            prefix = ""
        if format == "SQLite":
            prefix = ".sqlite"
        if format == "CSV":
            prefix = ".csv"

        # Remove a potential mapset
        file_name = vector_name.split("@")[0] + prefix
        archive_name = file_name + ".zip"
        # switch into the temporary working directory to use relative path for zip
        os.chdir(self.temp_file_path)

        module_name = "v.out.ogr"
        args = ["-e", "input=%s"%vector_name, "format=%s"%format,
                "output=%s"%file_name]

        if additional_options:
            args.extend(additional_options)

        # Export
        p = Process(exec_type="grass",
                         executable=module_name,
                         executable_params=args,
                         stdin_source=None)

        self._update_num_of_steps(1)
        self._run_module(p)

        # Compression
        compressed_output_path = os.path.join(self.temp_file_path, archive_name)

        executable = "/usr/bin/zip"
        args = ["-r", archive_name, file_name]

        p = Process(exec_type="exec",
                         executable=executable,
                         executable_params=args,
                         stdin_source=None)

        self._update_num_of_steps(1)
        self._run_process(p)

        return archive_name, compressed_output_path

    def _export_resources(self, use_raster_region=False):
        """Export all resources that were listed in the process chain description.

        Save all exported files in a temporary directory first, then copy the data to its destination
        after the export is finished. The temporary data will be finally removed.

        At the moment only raster layer export is supported.

        """
        for resource in self.resource_export_list:

            # Check for termination requests between the exports
            if self.resource_logger.get_termination(self.user_id, self.resource_id) is True:
                raise AsyncProcessTermination("Resource export was terminated by user request")

            # Raster export
            if resource["export"]["type"] in ["raster", "vector", "file"]:

                output_type = resource["export"]["type"]

                # Legacy code
                if "name" in resource:
                    file_name = resource["name"]
                if "value" in resource:
                    file_name = resource["value"]

                if output_type == "raster":
                    message = "Export raster layer <%s> with format %s"%(file_name, resource["export"]["format"])
                    self._send_resource_update(message)
                    output_name, output_path = self._export_raster(raster_name=file_name,
                                                                   format=resource["export"]["format"],
                                                                   use_raster_region=use_raster_region)

                if output_type == "vector":
                    message = "Export vector layer <%s> with format %s"%(file_name, resource["export"]["format"])
                    self._send_resource_update(message)
                    output_name, output_path = self._export_vector(vector_name=file_name,
                                                                   format=resource["export"]["format"])

                if output_type == "file":
                    return

                message = "Moving generated resources to final destination"
                self._send_resource_update(message)

                # Store the temporary file in the resource storage
                # and receive the resource URL
                resource_url = self.storage_interface.store_resource(output_path)

                self.resource_url_list.append(resource_url)

    def _execute(self):
        """Overwrite this function in subclasses

        Overwrite this function in subclasses

            - Setup user credentials
            - Setup the storage interface
            - Analyse the process chain
            - Initialize and create the temporal database and mapset
            - Run the modules
            - Export the results
            - Cleanup

        """
        # Setup the user credentials and logger
        self._setup()

        # Create and check the resource directory
        self.storage_interface.setup()

        AsyncEphemeralProcessing._execute(self)

        # Export all resources and generate the finish response
        self._export_resources()

    def _final_cleanup(self):
        """Overwrite this function in subclasses to perform the final cleanup
        """
        # Clean up and remove the temporary gisdbase
        self._cleanup()
        # Remove resource directories
        if "error" in self.run_state or "terminated" in self.run_state:
            self.storage_interface.remove_resources()
