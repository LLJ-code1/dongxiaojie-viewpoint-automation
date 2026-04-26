import Foundation
import Vision
import AppKit

struct OCRLine {
    let text: String
    let box: CGRect
    let confidence: Float
}

func recognizedLines(from path: String) throws -> [OCRLine] {
    let imageURL = URL(fileURLWithPath: path)
    guard let nsImage = NSImage(contentsOf: imageURL),
          let cgImage = nsImage.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "OCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Could not load \(path)"])
    }

    var lines: [OCRLine] = []
    let request = VNRecognizeTextRequest { request, error in
        if let error = error {
            fputs("OCR error for \(path): \(error)\n", stderr)
            return
        }

        let observations = (request.results as? [VNRecognizedTextObservation]) ?? []
        for observation in observations {
            if let candidate = observation.topCandidates(1).first {
                let text = candidate.string.replacingOccurrences(of: "\t", with: " ")
                lines.append(OCRLine(text: text, box: observation.boundingBox, confidence: candidate.confidence))
            }
        }
    }

    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.minimumTextHeight = 0.003

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    return lines.sorted { a, b in
        let dy = abs(a.box.midY - b.box.midY)
        if dy > 0.008 {
            return a.box.midY > b.box.midY
        }
        return a.box.minX < b.box.minX
    }
}

for path in CommandLine.arguments.dropFirst() {
    do {
        for line in try recognizedLines(from: path) {
            print("\(path)\t\(line.box.minX)\t\(line.box.minY)\t\(line.box.maxX)\t\(line.box.maxY)\t\(line.confidence)\t\(line.text)")
        }
    } catch {
        fputs("ERROR\t\(path)\t\(error)\n", stderr)
    }
}
