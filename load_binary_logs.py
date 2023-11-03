import pickle
import sys
import pprint
import glob

# Script to load all binary files in a directory and print them to a log file


def main():
    # directory with binary files, pass as command line argument
    directory = sys.argv[1]

    for file_path in glob.glob(f"{directory}/*[!log]"):
        request_response_data = []
        with open(file_path, "rb") as binary_file, open(f"{file_path}.log", "w") as log_file:
            while True:
                try:
                    request_response_data.append(pickle.load(binary_file))
                except EOFError:
                    break

            for data in request_response_data:
                pprint.pprint(data, width=80, stream=log_file)
                pprint.pprint(f"{'*' * 25}", stream=log_file)


if __name__ == "__main__":
    main()
