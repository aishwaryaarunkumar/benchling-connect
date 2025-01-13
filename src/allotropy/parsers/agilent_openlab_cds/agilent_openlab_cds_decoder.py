""" Decodes the .rslt folder file converted it to intermediate json"""
import os
from pathlib import Path
import tempfile
from typing import Any
import zipfile

import rainbow.agilent.chemstation as rb  # type: ignore
import xmltodict


def merge_peak_with_signal_name(
    peak_data: list[dict[str, Any]],
    signal_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Matches the signal IDs from the injections with those in the peaks and combines them accordingly.
    :param peak_data: peak data
    :param signal_data: signal id data
    :return: combined peak data
    """
    signal_id_to_name = {
        signal_id: signal_value
        for item in signal_data
        for signal_id, signal_value in item.items()
        if signal_id != "Name"
    }

    for peak in peak_data:
        signal_id = peak["Signal_ID"]
        if signal_id in signal_id_to_name:
            peak["Signal_ID"] = signal_id_to_name[signal_id]

    return peak_data


def decode_data_cubes(datacube_path: str) -> dict[str, Any]:
    """
    decodes the detection data to datacubes
    :param datacube_path: detection file path
    :return: decoded datacube
    """
    raw_data = rb.parse_ch(datacube_path)
    if ".CH" in os.path.basename(datacube_path):
        datacubes = {
            "Time": [time * 60 for time in raw_data.xlabels],
            "Intensity": [float(sublist[0]) for sublist in raw_data.data],
            "Metadata": raw_data.metadata,
        }
    else:
        datacubes = {
            "Time": [time * 60 for time in raw_data.xlabels],
            "Pressure": [float(sublist[0]) / 10 for sublist in raw_data.data],
            "Metadata": raw_data.metadata,
        }
    return datacubes


def extract_rx_file(
    temporary_input_path: str,
    zip_file_path: str,
    injection_signal: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Extracts the peak and its associated metadata from the rx file for each injection.
    :param temporary_input_path: rx file to be extracted
    :param zip_file_path: temporary unzip path
    :param injection_signal: each injection signal data
    :return: peak details along with its metadata
    """
    peak_details: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(dir=temporary_input_path) as temporary_directory:
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(temporary_directory)
            processed_file_path = next(
                iter(Path(temporary_directory).rglob("*InjectionACAML"))
            )
            with open(processed_file_path, encoding="utf-8-sig") as processed_file:
                peaks = xmltodict.parse(processed_file.read())
                for peak in peaks["ACAML"]["Doc"]["Content"]["Injections"]["Result"][
                    "SignalResult"
                ]:
                    peak_data = {}
                    if "Peak" in peak:
                        peak_data["Peak"] = peak["Peak"]
                        peak_data["Signal_ID"] = peak["Signal_ID"]["@id"]
                        peak_details.append(peak_data)

                peak_metadata_dict = {}
                if isinstance(
                    peaks["ACAML"]["Doc"]["Content"]["Injections"]["Result"][
                        "InjectionCompound"
                    ],
                    list,
                ):
                    for item in peaks["ACAML"]["Doc"]["Content"]["Injections"][
                        "Result"
                    ]["InjectionCompound"]:
                        peak_id = item.get("@id")
                        if peak_id:
                            identification = item.get("Identification", None)
                            identification_id = (
                                identification.get("Qualified", {})
                                .get("Peaks", {})
                                .get("Peak_ID", {})
                                .get("@id")
                            )
                            if identification_id:
                                peak_metadata_dict[identification_id] = item
                else:
                    peak_id = (
                        peaks["ACAML"]["Doc"]["Content"]["Injections"]["Result"][
                            "InjectionCompound"
                        ]["Identification"]
                        .get("Qualified", {})
                        .get("Peaks", {})
                        .get("Peak_ID", {})
                        .get("@id")
                    )
                    if peak_id:
                        peak_metadata_dict[peak_id] = peaks["ACAML"]["Doc"]["Content"][
                            "Injections"
                        ]["Result"]["InjectionCompound"]

                if isinstance(peak_details, list):
                    for peak_dict in peak_details:
                        if isinstance(peak_dict.get("Peak"), dict):
                            peak_id = peak_dict["Peak"]["@id"]
                            if peak_id in peak_metadata_dict:
                                peak_dict["Peak"]["Peak Metadata"] = peak_metadata_dict[
                                    peak_id
                                ]
                        elif isinstance(peak_dict.get("Peak"), list):
                            for peak in peak_dict["Peak"]:
                                peak_id = peak["@id"]
                                if peak_id in peak_metadata_dict:
                                    peak["Peak Metadata"] = peak_metadata_dict[peak_id]

    return merge_peak_with_signal_name(peak_details, injection_signal)


def extract_dx_file(
    temporary_input_path: str, zip_file_path: str, injection_metadata_data: Any
) -> list[dict[str, Any]]:
    """
    temporarily unzips the dx file and decodes the data and structures it
    :param temporary_input_path: temporary path to unzip file
    :param zip_file_path: compressed dx zip path
    :param injection_metadata_data: metadata of injection
    :return: chromatogram data, pump pressure data and its metadata for each injection
    """

    sample_data: dict[str, Any] = {}
    chromatogram_data: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(dir=temporary_input_path) as temporary_directory:
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(temporary_directory)
            acmd_filepath = next(iter(Path(temporary_directory).glob("*.acmd")))
            with open(acmd_filepath, encoding="utf-8-sig") as injection_file_data:
                acmd_data = injection_file_data.read()
                injection_data = xmltodict.parse(acmd_data)
                injection_data["ACMD"]["InjectionInfo"].pop("Signals")
                for sample_setup in injection_metadata_data["SampleSetup"]:
                    if (
                        sample_setup["IdentParam"]["Name"]
                        in injection_data["ACMD"]["InjectionInfo"]["SampleName"]
                    ):
                        sample_data["SampleSetup"] = sample_setup
                for sample_measurement in injection_metadata_data["SampleMeasurement"]:
                    if (
                        sample_measurement["IdentParam"]["Name"]
                        in injection_data["ACMD"]["InjectionInfo"]["SampleName"]
                    ):
                        sample_data["SampleMeasurement"] = sample_measurement

                sample_data["sequence_data"] = injection_metadata_data["sequence_data"]
                sample_data.update(injection_data["ACMD"]["InjectionInfo"])

                sample_data.update(injection_metadata_data["sequence_data"])
            for root, _dirs, files in os.walk(temporary_directory):
                for file in files:
                    file_path = os.path.join(str(root), file)
                    if (
                        file.endswith(".CH")
                        or injection_metadata_data["pump_pressure_filename"] in file
                    ):
                        chromatogram_data.append(decode_data_cubes(file_path))

        for each_chromatogram in chromatogram_data:
            each_chromatogram["Sample Data"] = sample_data
            each_chromatogram["file_name"] = os.path.basename(zip_file_path)
        return chromatogram_data


def extract_sqx_file(temporary_input_path: str, zip_file_path: str) -> dict[str, Any]:
    """
    unzips the sqx file and retrieves analysis method path
    :param temporary_input_path: temporary unzip file path
    :param zip_file_path: sqx file path
    :return: structured analysis method data
    """
    with tempfile.TemporaryDirectory(dir=temporary_input_path) as temporary_directory:
        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(temporary_directory)
            sequence_sample_data = {}
            sample_file_path = list(Path(temporary_directory).rglob("*SampleListPart"))[
                1
            ]
            with open(sample_file_path) as sample_file:
                sequence_sample_data["AnalysisMethod"] = xmltodict.parse(
                    sample_file.read()
                )["SequenceTable"]["anyType"][0]["AnalysisMethod"]
                return sequence_sample_data


def decode_acaml_data(
    acaml_content: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """
    structures the acaml file data
    :param acaml_content: decoded acaml data
    :return: structured acaml content
    """
    metadata_data: dict[str, Any] = {}
    instrument_data: dict[str, Any] = {}
    pump_pressure_file: dict[str, Any] = {}
    signal_details: dict[str, Any] = {"Signal details": []}

    content_data = acaml_content["ACAML"]["Doc"]["Content"]
    instrument_fields = [
        "Name",
        "Technique",
        "@id",
        "Module",
        "AcquisitionApplication",
        "CreatedByUser",
        "CreationDate",
    ]
    for key in instrument_fields:
        if key in content_data["Resources"]["Instrument"]:
            instrument_data[key] = content_data["Resources"]["Instrument"][key]
        elif key in content_data["Injections"]["MeasData"][0]:
            instrument_data[key] = content_data["Injections"]["MeasData"][0][key]
        elif key in acaml_content["ACAML"]["Doc"]["DocInfo"]:
            instrument_data[key] = acaml_content["ACAML"]["Doc"]["DocInfo"][key]
    for measurements in content_data["Injections"]["MeasData"]:
        signal_data = {}
        for signals in measurements["Signal"]:
            signal_data["Name"] = signals["BinaryData"]["DataItem"]["Name"].split(".")[
                0
            ]
            signal_data[signals["@id"]] = signals["Name"]
            if "Pressure" in signals["Description"]:
                pump_pressure_file[
                    signals["BinaryData"]["DataItem"]["Name"].split(".")[0]
                ] = signals["TraceID"]
        signal_details["Signal details"].append(signal_data)
    metadata_data["Instrument"] = instrument_data
    metadata_data["SeparationMedium"] = content_data["Resources"]["SeparationMedium"]
    metadata_data["SampleSetup"] = content_data["Samples"]["Setup"]
    metadata_data["SampleMeasurement"] = content_data["Samples"]["MeasData"]

    return metadata_data, pump_pressure_file, signal_details


def decode_data(input_path: str) -> dict[str, Any]:
    """
    decoded the files in input folder path and returns a structured data
    :param input_path: input folder path
    :return: structured intermediate json
    """
    intermediate_json: dict[str, Any] = {}
    injection_data: dict[str, Any] = {}
    total_injection_chromatogram_details: list[dict[str, Any]] = []
    total_peak_details: list[dict[str, Any]] = []

    acaml_path = next(iter(Path(input_path).glob("*acaml")))
    with open(acaml_path, encoding="utf-8-sig") as acaml_file_data:
        acaml_file_content = acaml_file_data.read()
        decoded_acaml_content = xmltodict.parse(acaml_file_content)
    (
        intermediate_metadata,
        pump_pressure_file,
        injection_signal_details,
    ) = decode_acaml_data(decoded_acaml_content)
    injection_data["total_pressure_files"] = pump_pressure_file
    injection_data["SampleSetup"] = intermediate_metadata["SampleSetup"]
    injection_data["SampleMeasurement"] = intermediate_metadata["SampleMeasurement"]
    injection_data["signal_details"] = injection_signal_details
    intermediate_metadata.pop("SampleSetup")
    intermediate_metadata.pop("SampleMeasurement")
    intermediate_json["Metadata"] = intermediate_metadata

    sequence_file_path = next(iter(Path(input_path).glob("*.sqx")))
    sequence_data = extract_sqx_file(
        str(os.path.dirname(input_path)), str(sequence_file_path)
    )
    injection_data["sequence_data"] = sequence_data
    dx_files = list(Path(input_path).glob("*.dx"))
    for dx_file in dx_files:
        injection_file_name = str(os.path.basename(dx_file))
        for key, values in injection_data["total_pressure_files"].items():
            if key in injection_file_name:
                injection_data["pump_pressure_filename"] = values
        total_injection_chromatogram_details.extend(
            extract_dx_file(
                str(os.path.dirname(input_path)), str(dx_file), injection_data
            )
        )
    rx_files = list(Path(input_path).glob("*.rx"))
    for rx_file in rx_files:
        processed_peak_data: dict[str, Any] = {}
        peak_details = extract_rx_file(
            str(os.path.dirname(input_path)),
            str(rx_file),
            injection_data["signal_details"]["Signal details"],
        )
        processed_peak_data["file_name"] = os.path.basename(rx_file)
        processed_peak_data["peak_details"] = peak_details
        total_peak_details.append(processed_peak_data)
    for injection_details in total_injection_chromatogram_details:
        for peaks_data in total_peak_details:
            if (
                Path(injection_details["file_name"]).stem
                == Path(peaks_data["file_name"]).stem
            ):
                peak_details_data = peaks_data["peak_details"]
                for peak_detail in peak_details_data:
                    if isinstance(peak_detail, dict):
                        signal_name = injection_details["Metadata"]["signal"].split(
                            ","
                        )[0]
                        peak_signal = peak_detail["Signal_ID"]
                        if peak_signal == signal_name:
                            if isinstance(peak_detail["Peak"], list):
                                injection_details.update(peak_detail)
                            if isinstance(peak_detail["Peak"], dict):
                                peak_detail["Peak"] = [peak_detail["Peak"]]
                                injection_details.update(peak_detail)

    intermediate_json["Result Data"] = total_injection_chromatogram_details
    intermediate_json["Sample Count"] = {
        "count": len(total_injection_chromatogram_details)
    }
    return intermediate_json