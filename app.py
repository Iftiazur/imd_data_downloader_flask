from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
import imdlib as imd
import zipfile
from io import BytesIO
import glob

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})


OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../output'))

@app.route('/download', methods=['POST'])
def download():
    grd_files = []
    output_files = []

    try:
        data = request.json
        start_yr = int(data['start_yr'])
        end_yr = int(data['end_yr'])
        lat = float(data['lat'])
        lon = float(data['lon'])
        variables = data['variables']

        lat_rounded = round(lat, 2)
        lon_rounded = round(lon, 2)

        print(f"Received lat: {lat}, lon: {lon} (rounded: {lat_rounded}, {lon_rounded})")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        for var in variables:
            print(f"Fetching {var} data for {start_yr}-{end_yr} at ({lat_rounded}, {lon_rounded})")
            imd.get_data(var, start_yr, end_yr, fn_format='yearwise')

            # Track .grd files created
            grd_pattern = os.path.join(os.getcwd(), f"{var}_*.grd")
            grd_files.extend(glob.glob(grd_pattern))

            ds = imd.open_data(var, start_yr, end_yr, fn_format='yearwise')
            output_path = os.path.join(OUTPUT_DIR, f"{var}_{lat_rounded:.2f}_{lon_rounded:.2f}.csv")
            ds.to_csv(file_name=output_path, lat=lat_rounded, lon=lon_rounded)

            if not os.path.exists(output_path):
                matches = glob.glob(os.path.join(OUTPUT_DIR, f"{var}_*.csv"))
                if matches:
                    output_files.append(matches[0])
                else:
                    return jsonify({
                        "error": f"Could not extract data for lat={lat}, lon={lon}. Please use a valid location within India."
                    }), 400
            else:
                output_files.append(output_path)

        # Return file(s)
        if len(output_files) == 1:
            response = send_file(output_files[0], as_attachment=True)
        else:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for file in output_files:
                    zf.write(file, os.path.basename(file))
            zip_buffer.seek(0)
            response = send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name='weather_data.zip'
            )

        return response

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        # Cleanup .grd files
        for f in grd_files:
            try:
                os.remove(f)
                print(f"Deleted .grd: {f}")
            except Exception as cleanup_error:
                print(f"Failed to delete {f}: {cleanup_error}")

        # Cleanup .csv files
        for f in output_files:
            try:
                os.remove(f)
                print(f"Deleted .csv: {f}")
            except Exception as cleanup_error:
                print(f"Failed to delete {f}: {cleanup_error}")

if __name__ == '__main__':
    from waitress import serve
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
