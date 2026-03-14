import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FileUploader } from './FileUploader';

const mockUploadFile = jest.fn();

jest.mock('@/lib/api', () => {
  class MockApiError extends Error {
    code: string;
    status: number;

    constructor(message: string, code = 'UNKNOWN_ERROR', status = 500) {
      super(message);
      this.name = 'ApiError';
      this.code = code;
      this.status = status;
    }
  }

  return {
    uploadFile: (...args: unknown[]) => mockUploadFile(...args),
    ApiError: MockApiError,
  };
});

function createMockFile(name: string, size = 1024) {
  return new File([new Uint8Array(size)], name, {
    type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  });
}

describe('FileUploader', () => {
  beforeEach(() => {
    mockUploadFile.mockReset();
    mockUploadFile.mockImplementation(async (file: File) => ({
      file_path: `D:/UploadFiles/${file.name}`,
      file_name: file.name,
      original_name: file.name,
    }));
  });

  it('keeps upload entry visible and renders uploaded file in the same card for single file mode', async () => {
    const user = userEvent.setup();
    const onFilesChange = jest.fn();

    render(
      <FileUploader
        label="模板文件（可选）"
        description="上传模板 Word 文件"
        autoUpload={true}
        multiple={false}
        fileType="clean_draft"
        onFilesChange={onFilesChange}
      />
    );

    const card = screen.getByTestId('file-uploader-clean_draft-card');
    const input = card.querySelector('input[type="file"]');
    const file = createMockFile('template.docx');

    expect(input).not.toBeNull();
    await user.upload(input as HTMLInputElement, file);

    await waitFor(() => expect(onFilesChange).toHaveBeenCalledWith(expect.any(Array)));

    expect(within(card).getByText('模板文件（可选）')).toBeInTheDocument();
    expect(within(card).getByText('单文件上传')).toBeInTheDocument();
    expect(within(card).getByTestId('file-uploader-clean_draft-files')).toBeInTheDocument();
    expect(within(card).getByText('template.docx')).toBeInTheDocument();
  });

  it('renders multiple uploaded files as a vertical list in params mode', async () => {
    const user = userEvent.setup();

    render(
      <FileUploader
        label="技术参数文件（必填）"
        description="上传技术参数 Word 文件"
        autoUpload={true}
        multiple={true}
        maxFiles={10}
        fileType="params"
      />
    );

    const card = screen.getByTestId('file-uploader-params-card');
    const input = card.querySelector('input[type="file"]');
    const fileA = createMockFile('params-a.docx', 2048);
    const fileB = createMockFile('params-b.docx', 4096);

    expect(input).not.toBeNull();
    await user.upload(input as HTMLInputElement, [fileA, fileB]);

    await waitFor(() => expect(within(card).getByText('params-a.docx')).toBeInTheDocument());
    expect(within(card).getByText('params-b.docx')).toBeInTheDocument();

    const list = within(card).getByTestId('file-uploader-params-files');
    expect(list.children.length).toBe(3);
    expect(within(card).getAllByRole('button', { name: /删除文件/ })).toHaveLength(2);
  });

  it('supports deleting uploaded files', async () => {
    const user = userEvent.setup();
    const onFilesChange = jest.fn();

    render(
      <FileUploader
        label="技术参数文件（必填）"
        description="上传技术参数 Word 文件"
        autoUpload={true}
        multiple={true}
        fileType="params"
        onFilesChange={onFilesChange}
      />
    );

    const card = screen.getByTestId('file-uploader-params-card');
    const input = card.querySelector('input[type="file"]');
    const file = createMockFile('params-to-delete.docx');

    expect(input).not.toBeNull();
    await user.upload(input as HTMLInputElement, file);

    await waitFor(() =>
      expect(within(card).getByText('params-to-delete.docx')).toBeInTheDocument()
    );

    await user.click(within(card).getByRole('button', { name: '删除文件 params-to-delete.docx' }));

    await waitFor(() =>
      expect(within(card).queryByText('params-to-delete.docx')).not.toBeInTheDocument()
    );
    expect(onFilesChange).toHaveBeenLastCalledWith([]);
  });
});
